import json

import pytest

from nova.agents import AGENTS, AGENTS_BY_NAME, AgentRouter, GENERAL_AGENT
from nova.agents.catalog import FILE_AGENT, MEMORY_AGENT, SYSTEM_AGENT
from nova.audit import AuditLog
from nova.llm.fake import ScriptedProvider
from nova.orchestrator import Orchestrator
from nova.permissions import DEFAULT_POLICY, PermissionEngine
from nova.planner import Planner
from nova.tools.builtin import build_default_registry
from nova.tools.registry import UnknownToolError


def _router(tmp_path, responses):
    return AgentRouter(
        provider=ScriptedProvider(responses), audit=AuditLog(tmp_path / "audit.jsonl")
    )


# --- catalogue integrity -------------------------------------------------


def test_agent_names_are_unique():
    names = [a.name for a in AGENTS]
    assert len(names) == len(set(names))


def test_every_agent_tool_exists_in_the_default_registry():
    registry = build_default_registry()
    for agent in AGENTS:
        for tool in agent.tools:
            try:
                registry.get(tool)
            except UnknownToolError:  # pragma: no cover - failure path
                pytest.fail(f"agent {agent.name!r} references unknown tool {tool!r}")


def test_general_agent_has_no_tool_restriction():
    assert GENERAL_AGENT.tools == ()


def test_every_agent_has_a_description_and_guidance():
    for agent in AGENTS:
        assert agent.description.strip(), agent.name
        assert agent.guidance.strip(), agent.name


# --- routing -------------------------------------------------------------


@pytest.mark.parametrize(
    "reply,expected",
    [
        ("files", FILE_AGENT),
        ("system", SYSTEM_AGENT),
        ("memory", MEMORY_AGENT),
        ("general", GENERAL_AGENT),
    ],
)
def test_router_maps_a_clean_reply_to_its_agent(tmp_path, reply, expected):
    assert _router(tmp_path, [reply]).route("do a thing", []) is expected


def test_router_tolerates_a_chatty_reply(tmp_path):
    router = _router(tmp_path, ["I think the system specialist is best here."])

    assert router.route("check my disk space", []) is SYSTEM_AGENT


def test_router_is_case_insensitive(tmp_path):
    assert _router(tmp_path, ["MEMORY"]).route("remember this", []) is MEMORY_AGENT


def test_router_falls_back_when_the_reply_names_nothing_known(tmp_path):
    router = _router(tmp_path, ["I have no idea what you want"])

    assert router.route("???", []) is GENERAL_AGENT


def test_router_falls_back_on_empty_reply(tmp_path):
    assert _router(tmp_path, [""]).route("hello", []) is GENERAL_AGENT


def test_router_audits_its_choice(tmp_path):
    audit = AuditLog(tmp_path / "audit.jsonl")
    router = AgentRouter(provider=ScriptedProvider(["files"]), audit=audit)

    router.route("read a file", [])

    events = [e for e in audit.read_all() if e.event_type == "agent_selected"]
    assert len(events) == 1
    assert events[0].payload["agent"] == "files"


def test_router_prompt_lists_every_agent(tmp_path):
    provider = ScriptedProvider(["general"])
    AgentRouter(provider=provider, audit=AuditLog(tmp_path / "a.jsonl")).route("x", [])

    system, _ = provider.calls[0]
    for agent in AGENTS:
        assert agent.name in system


# --- scoping -------------------------------------------------------------


def test_subset_narrows_the_registry_to_the_agent_tools():
    scoped = build_default_registry().subset(FILE_AGENT.tools)

    assert [s.name for s in scoped.list_specs()] == list(FILE_AGENT.tools)


def test_subset_with_no_names_returns_everything():
    registry = build_default_registry()

    assert registry.subset(()) is registry


def test_planner_only_sees_the_scoped_tools():
    registry = build_default_registry()
    provider = ScriptedProvider([json.dumps({"summary": "s", "steps": []})])
    planner = Planner(provider=provider, registry=registry, max_steps=8)

    planner.plan("read a file", [], registry=registry.subset(FILE_AGENT.tools))

    system, _ = provider.calls[0]
    assert "file_read" in system
    assert "shell_run" not in system


def test_planner_rejects_a_tool_outside_the_agent_scope():
    from nova.planner import PlanParseError

    registry = build_default_registry()
    response = json.dumps(
        {
            "summary": "s",
            "steps": [{"tool": "shell_run", "arguments": {"command": "ls"}, "rationale": "r"}],
        }
    )
    planner = Planner(
        provider=ScriptedProvider([response]), registry=registry, max_steps=8
    )

    with pytest.raises(PlanParseError, match="shell_run"):
        planner.plan("run something", [], registry=registry.subset(FILE_AGENT.tools))


def test_planner_prompt_carries_the_agent_guidance():
    registry = build_default_registry()
    provider = ScriptedProvider([json.dumps({"summary": "s", "steps": []})])
    planner = Planner(provider=provider, registry=registry, max_steps=8)

    planner.plan("x", [], guidance=SYSTEM_AGENT.guidance)

    system, _ = provider.calls[0]
    assert "read-only inspection command" in system


# --- end to end through the orchestrator ---------------------------------


def _orchestrator(tool_context, router_reply, plan_json, reply="done"):
    registry = build_default_registry()
    audit = AuditLog(tool_context.config.audit_log_path)
    router = AgentRouter(provider=ScriptedProvider([router_reply]), audit=audit)
    provider = ScriptedProvider([plan_json, reply])
    return Orchestrator(
        planner=Planner(provider=provider, registry=registry, max_steps=8),
        registry=registry,
        permissions=PermissionEngine(DEFAULT_POLICY, audit),
        provider=provider,
        context=tool_context,
        router=router,
    )


def test_orchestrator_reports_the_selected_agent(tool_context):
    (tool_context.config.workspace_root / "a.txt").write_text("alpha", encoding="utf-8")
    plan = json.dumps(
        {
            "summary": "read it",
            "steps": [{"tool": "file_read", "arguments": {"path": "a.txt"}, "rationale": "r"}],
        }
    )

    result = _orchestrator(tool_context, "files", plan).handle("read a.txt", lambda s: True)

    assert result.agent is FILE_AGENT
    assert result.outcomes[0].result.output == "alpha"


def test_orchestrator_without_a_router_reports_no_agent(tool_context):
    registry = build_default_registry()
    audit = AuditLog(tool_context.config.audit_log_path)
    provider = ScriptedProvider([json.dumps({"summary": "hi", "steps": []})])
    orchestrator = Orchestrator(
        planner=Planner(provider=provider, registry=registry, max_steps=8),
        registry=registry,
        permissions=PermissionEngine(DEFAULT_POLICY, audit),
        provider=provider,
        context=tool_context,
    )

    assert orchestrator.handle("hi", lambda s: True).agent is None


def test_out_of_scope_tool_is_refused_end_to_end(tool_context):
    """Routed to `files`, the model asks for shell_run anyway. It must not run."""
    plan = json.dumps(
        {
            "summary": "sneak a shell in",
            "steps": [
                {"tool": "shell_run", "arguments": {"command": "echo hi"}, "rationale": "r"}
            ],
        }
    )

    result = _orchestrator(tool_context, "files", plan).handle("read a.txt", lambda s: True)

    assert result.plan is None
    assert result.outcomes == []
    assert "shell_run" in result.reply


def test_agent_choice_is_recorded_in_the_audit_log(tool_context):
    plan = json.dumps({"summary": "nothing to do", "steps": []})

    _orchestrator(tool_context, "memory", plan).handle("what do you know?", lambda s: True)

    events = AuditLog(tool_context.config.audit_log_path).read_all()
    selected = [e for e in events if e.event_type == "agent_selected"]
    created = [e for e in events if e.event_type == "plan_created"]
    assert selected[0].payload["agent"] == "memory"
    assert created[0].payload["agent"] == "memory"


def test_agents_by_name_covers_the_catalogue():
    assert set(AGENTS_BY_NAME) == {a.name for a in AGENTS}
