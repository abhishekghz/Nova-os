import json

import pytest
from fastapi.testclient import TestClient

from nova.agents.router import AgentRouter
from nova.api.app import create_app
from nova.api.sessions import SessionManager
from nova.audit import AuditLog
from nova.llm.fake import ScriptedProvider
from nova.orchestrator import Orchestrator
from nova.permissions import DEFAULT_POLICY, PermissionEngine
from nova.planner import Planner
from nova.tools.builtin import build_default_registry


def _plan(steps, summary="s"):
    return json.dumps({"summary": summary, "steps": steps})


CHATTY = _plan([], summary="Hello there.")


def _make_orchestrator(tool_context, responses, router_reply=None):
    registry = build_default_registry()
    provider = ScriptedProvider(responses)
    audit = AuditLog(tool_context.config.audit_log_path)
    router = (
        AgentRouter(provider=ScriptedProvider([router_reply]), audit=audit)
        if router_reply
        else None
    )
    return Orchestrator(
        planner=Planner(provider=provider, registry=registry, max_steps=8),
        registry=registry,
        permissions=PermissionEngine(DEFAULT_POLICY, audit),
        provider=provider,
        context=tool_context,
        router=router,
    )


@pytest.fixture
def client(tool_context):
    app = create_app(
        config=tool_context.config,
        orchestrator_factory=lambda: _make_orchestrator(tool_context, [CHATTY] * 20),
        memory=tool_context.memory,
    )
    return TestClient(app), tool_context.config.api_key


# --- health and auth -----------------------------------------------------


def test_health_needs_no_key(client):
    http, _ = client

    response = http.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_chat_without_a_key_is_rejected(client):
    http, _ = client

    response = http.post("/chat", json={"message": "hi"})

    assert response.status_code == 401


def test_chat_with_a_wrong_key_is_rejected(client):
    http, _ = client

    response = http.post("/chat", json={"message": "hi"}, headers={"X-API-Key": "nope"})

    assert response.status_code == 401


def test_rejected_auth_is_audited(client, tool_context):
    http, _ = client

    http.post("/chat", json={"message": "hi"}, headers={"X-API-Key": "nope"})

    events = AuditLog(tool_context.config.audit_log_path).read_all()
    assert any(e.event_type == "api_auth_rejected" for e in events)


# --- chat ----------------------------------------------------------------


def test_chat_with_a_valid_key_replies(client):
    http, key = client

    response = http.post(
        "/chat", json={"message": "hi"}, headers={"X-API-Key": key}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Hello there."
    assert body["session_id"] == "default"
    assert body["steps"] == []


def test_chat_rejects_an_empty_message(client):
    http, key = client

    response = http.post("/chat", json={"message": ""}, headers={"X-API-Key": key})

    assert response.status_code == 422


def test_rest_denies_confirm_steps_by_default(tool_context):
    """REST cannot ask, so a write must not happen unless opted into."""
    plan = _plan(
        [{"tool": "file_write", "arguments": {"path": "o.txt", "content": "x"}, "rationale": "r"}]
    )
    app = create_app(
        config=tool_context.config,
        orchestrator_factory=lambda: _make_orchestrator(tool_context, [plan, "stopped"]),
        memory=tool_context.memory,
    )
    http = TestClient(app)

    body = http.post(
        "/chat",
        json={"message": "write it"},
        headers={"X-API-Key": tool_context.config.api_key},
    ).json()

    assert body["steps"][0]["decision"] == "deny"
    assert not (tool_context.config.workspace_root / "o.txt").exists()


def test_rest_auto_approve_lets_the_write_through(tool_context):
    plan = _plan(
        [{"tool": "file_write", "arguments": {"path": "o.txt", "content": "x"}, "rationale": "r"}]
    )
    app = create_app(
        config=tool_context.config,
        orchestrator_factory=lambda: _make_orchestrator(tool_context, [plan, "done"]),
        memory=tool_context.memory,
    )
    http = TestClient(app)

    body = http.post(
        "/chat",
        json={"message": "write it", "auto_approve": True},
        headers={"X-API-Key": tool_context.config.api_key},
    ).json()

    assert body["steps"][0]["ok"] is True
    assert (tool_context.config.workspace_root / "o.txt").read_text(encoding="utf-8") == "x"


def test_chat_reports_the_routed_agent(tool_context):
    app = create_app(
        config=tool_context.config,
        orchestrator_factory=lambda: _make_orchestrator(
            tool_context, [CHATTY], router_reply="memory"
        ),
        memory=tool_context.memory,
    )
    http = TestClient(app)

    body = http.post(
        "/chat", json={"message": "hi"}, headers={"X-API-Key": tool_context.config.api_key}
    ).json()

    assert body["agent"] == "memory"


# --- sessions ------------------------------------------------------------


def test_sessions_are_isolated(client):
    http, key = client
    headers = {"X-API-Key": key}

    http.post("/chat", json={"message": "one", "session_id": "a"}, headers=headers)
    http.post("/chat", json={"message": "two", "session_id": "b"}, headers=headers)

    assert set(http.get("/sessions", headers=headers).json()["sessions"]) >= {"a", "b"}


def test_a_session_can_be_dropped(client):
    http, key = client
    headers = {"X-API-Key": key}
    http.post("/chat", json={"message": "one", "session_id": "temp"}, headers=headers)

    assert http.delete("/sessions/temp", headers=headers).json()["dropped"] is True
    assert http.delete("/sessions/temp", headers=headers).json()["dropped"] is False


# --- tools, audit, memory ------------------------------------------------


def test_tools_endpoint_lists_the_registry(client):
    http, key = client

    body = http.get("/tools", headers={"X-API-Key": key}).json()

    names = [t["name"] for t in body["tools"]]
    assert "file_read" in names
    assert "shell_run" in names
    assert all("risk" in t for t in body["tools"])


def test_audit_endpoint_returns_events(client):
    http, key = client
    headers = {"X-API-Key": key}
    http.post("/chat", json={"message": "hi"}, headers=headers)

    body = http.get("/audit", headers=headers).json()

    assert any(e["event_type"] == "api_chat" for e in body["events"])


def test_audit_limit_is_clamped(client):
    http, key = client

    response = http.get("/audit?limit=100000", headers={"X-API-Key": key})

    assert response.status_code == 200


def test_memory_round_trip_over_http(client):
    http, key = client
    headers = {"X-API-Key": key}

    http.post(
        "/memory",
        json={"kind": "preference", "key": "editor", "value": "VS Code"},
        headers=headers,
    )
    body = http.get("/memory?query=editor", headers=headers).json()

    assert body["memories"][0]["value"] == "VS Code"


def test_memory_rejects_an_unknown_kind(client):
    http, key = client

    response = http.post(
        "/memory",
        json={"kind": "bogus", "key": "k", "value": "v"},
        headers={"X-API-Key": key},
    )

    assert response.status_code == 400


def test_memory_delete(client):
    http, key = client
    headers = {"X-API-Key": key}
    http.post(
        "/memory", json={"kind": "fact", "key": "k", "value": "v"}, headers=headers
    )

    assert http.delete("/memory/k", headers=headers).json()["forgotten"] is True


# --- websocket -----------------------------------------------------------


def test_websocket_rejects_a_bad_key(client):
    http, _ = client

    with pytest.raises(Exception):
        with http.websocket_connect("/ws/chat?api_key=wrong"):
            pass


def test_websocket_chat_replies(client):
    http, key = client

    with http.websocket_connect(f"/ws/chat?api_key={key}") as ws:
        ws.send_json({"message": "hi"})
        frame = ws.receive_json()

    assert frame["type"] == "reply"
    assert frame["reply"] == "Hello there."


def test_websocket_rejects_an_empty_message(client):
    http, key = client

    with http.websocket_connect(f"/ws/chat?api_key={key}") as ws:
        ws.send_json({"message": "   "})
        frame = ws.receive_json()

    assert frame["type"] == "error"


def test_websocket_asks_for_approval_and_honours_yes(tool_context):
    plan = _plan(
        [{"tool": "file_write", "arguments": {"path": "w.txt", "content": "yes"}, "rationale": "r"}]
    )
    app = create_app(
        config=tool_context.config,
        orchestrator_factory=lambda: _make_orchestrator(tool_context, [plan, "wrote it"]),
        memory=tool_context.memory,
    )
    http = TestClient(app)
    key = tool_context.config.api_key

    with http.websocket_connect(f"/ws/chat?api_key={key}") as ws:
        ws.send_json({"message": "write w.txt"})
        ask = ws.receive_json()
        assert ask["type"] == "approval_request"
        assert ask["tool"] == "file_write"
        ws.send_json({"approve": True})
        reply = ws.receive_json()

    assert reply["type"] == "reply"
    assert (tool_context.config.workspace_root / "w.txt").read_text(encoding="utf-8") == "yes"


def test_websocket_approval_denial_blocks_the_write(tool_context):
    plan = _plan(
        [{"tool": "file_write", "arguments": {"path": "n.txt", "content": "no"}, "rationale": "r"}]
    )
    app = create_app(
        config=tool_context.config,
        orchestrator_factory=lambda: _make_orchestrator(tool_context, [plan, "refused"]),
        memory=tool_context.memory,
    )
    http = TestClient(app)
    key = tool_context.config.api_key

    with http.websocket_connect(f"/ws/chat?api_key={key}") as ws:
        ws.send_json({"message": "write n.txt"})
        ws.receive_json()
        ws.send_json({"approve": False})
        reply = ws.receive_json()

    assert reply["steps"][0]["decision"] == "deny"
    assert not (tool_context.config.workspace_root / "n.txt").exists()


# --- session manager -----------------------------------------------------


def test_session_manager_reuses_instances():
    made = []

    def factory():
        made.append(1)
        return object()

    manager = SessionManager(factory)
    first = manager.get("a")
    second = manager.get("a")

    assert first is second
    assert len(made) == 1
    assert len(manager) == 1
