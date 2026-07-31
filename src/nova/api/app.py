"""REST and WebSocket API for NOVA.

This is the gateway a remote client (phone, web dashboard, another service)
talks to. It reuses the exact same Orchestrator, permission engine and audit
log as the local CLI, so a remote request is governed by identical rules.

Approval handling differs by transport, deliberately:

* REST has no way to ask a follow-up question mid-request, so a step needing
  confirmation is **denied** unless the caller opted in with `auto_approve`.
* WebSocket can ask, so it sends an `approval_request` frame and waits for the
  client's answer. That is the seam a phone app plugs into.
"""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Callable
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Header, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from nova.audit import AuditLog
from nova.config import NovaConfig
from nova.memory.store import MemoryStore, UnknownMemoryKindError
from nova.orchestrator import Orchestrator, TurnResult
from nova.planner import PlanStep
from nova.api.sessions import SessionManager

API_VERSION = "1"


# --- request/response models --------------------------------------------


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    session_id: str = "default"
    auto_approve: bool = False


class StepView(BaseModel):
    tool: str
    arguments: dict
    decision: str
    ok: bool | None
    output: str | None
    error: str | None


class ChatResponse(BaseModel):
    reply: str
    agent: str | None
    session_id: str
    steps: list[StepView]


class MemoryWrite(BaseModel):
    kind: str
    key: str = Field(min_length=1)
    value: str = Field(min_length=1)


def _to_steps(result: TurnResult) -> list[StepView]:
    return [
        StepView(
            tool=outcome.step.tool,
            arguments=outcome.step.arguments,
            decision=outcome.decision.value,
            ok=None if outcome.result is None else outcome.result.ok,
            output=None if outcome.result is None else outcome.result.output,
            error=None if outcome.result is None else outcome.result.error,
        )
        for outcome in result.outcomes
    ]


def create_app(
    config: NovaConfig,
    orchestrator_factory: Callable[[], Orchestrator],
    memory: MemoryStore | None = None,
) -> FastAPI:
    """Build the API around an existing NOVA configuration."""
    app = FastAPI(title="NOVA", version=API_VERSION)
    sessions = SessionManager(orchestrator_factory)
    audit = AuditLog(config.audit_log_path)

    app.state.config = config
    app.state.sessions = sessions
    app.state.memory = memory

    def require_key(x_api_key: str = Header(default="")) -> None:
        """Constant-time API key check on every non-public route."""
        if not secrets.compare_digest(x_api_key, config.api_key):
            audit.record("api_auth_rejected", {"supplied_key_length": len(x_api_key)})
            raise HTTPException(status_code=401, detail="invalid or missing X-API-Key")

    # --- public ----------------------------------------------------------

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "version": API_VERSION}

    # --- authenticated ---------------------------------------------------

    @app.get("/tools", dependencies=[Depends(require_key)])
    def tools() -> dict[str, Any]:
        registry = sessions.get("__introspect__")._registry
        return {
            "tools": [
                {"name": s.name, "description": s.description, "risk": s.risk.value}
                for s in registry.list_specs()
            ]
        }

    @app.post("/chat", dependencies=[Depends(require_key)], response_model=ChatResponse)
    def chat(request: ChatRequest) -> ChatResponse:
        orchestrator = sessions.get(request.session_id)
        audit.record(
            "api_chat", {"session": request.session_id, "auto_approve": request.auto_approve}
        )
        result = orchestrator.handle(
            request.message, lambda step: request.auto_approve
        )
        return ChatResponse(
            reply=result.reply,
            agent=result.agent.name if result.agent else None,
            session_id=request.session_id,
            steps=_to_steps(result),
        )

    @app.get("/sessions", dependencies=[Depends(require_key)])
    def list_sessions() -> dict[str, Any]:
        return {"sessions": sessions.ids()}

    @app.delete("/sessions/{session_id}", dependencies=[Depends(require_key)])
    def drop_session(session_id: str) -> dict[str, Any]:
        return {"dropped": sessions.drop(session_id)}

    @app.get("/audit", dependencies=[Depends(require_key)])
    def read_audit(limit: int = 50) -> dict[str, Any]:
        limit = max(1, min(limit, 500))
        events = audit.read_all()[-limit:]
        return {
            "events": [
                {
                    "event_id": e.event_id,
                    "timestamp": e.timestamp,
                    "event_type": e.event_type,
                    "payload": e.payload,
                }
                for e in events
            ]
        }

    @app.get("/memory", dependencies=[Depends(require_key)])
    def read_memory(query: str = "") -> dict[str, Any]:
        if memory is None:
            raise HTTPException(status_code=503, detail="memory is not enabled")
        records = memory.recall(query) if query else memory.all()
        return {
            "memories": [
                {"kind": r.kind, "key": r.key, "value": r.value, "updated_at": r.updated_at}
                for r in records
            ]
        }

    @app.post("/memory", dependencies=[Depends(require_key)])
    def write_memory(entry: MemoryWrite) -> dict[str, Any]:
        if memory is None:
            raise HTTPException(status_code=503, detail="memory is not enabled")
        try:
            record = memory.remember(entry.kind, entry.key, entry.value)
        except UnknownMemoryKindError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"kind": record.kind, "key": record.key, "value": record.value}

    @app.delete("/memory/{key}", dependencies=[Depends(require_key)])
    def delete_memory(key: str) -> dict[str, Any]:
        if memory is None:
            raise HTTPException(status_code=503, detail="memory is not enabled")
        return {"forgotten": memory.forget(key)}

    # --- websocket -------------------------------------------------------

    @app.websocket("/ws/chat")
    async def ws_chat(websocket: WebSocket) -> None:
        """Interactive chat with real remote approval.

        Frames from the client: {"message": str, "session_id": str?}
                                {"approve": bool}   (answering an approval_request)
        Frames to the client:   {"type": "approval_request", "tool", "arguments", "rationale"}
                                {"type": "reply", "reply", "agent", "steps"}
                                {"type": "error", "detail"}
        """
        supplied = websocket.headers.get("x-api-key", "") or websocket.query_params.get(
            "api_key", ""
        )
        if not secrets.compare_digest(supplied, config.api_key):
            audit.record("api_auth_rejected", {"transport": "websocket"})
            await websocket.close(code=4401)
            return

        await websocket.accept()
        loop = asyncio.get_running_loop()

        try:
            while True:
                payload = await websocket.receive_json()
                message = payload.get("message")
                if not isinstance(message, str) or not message.strip():
                    await websocket.send_json(
                        {"type": "error", "detail": "'message' must be a non-empty string"}
                    )
                    continue

                session_id = payload.get("session_id", "default")
                orchestrator = sessions.get(session_id)

                def confirm(step: PlanStep) -> bool:
                    """Ask the remote client. Runs on the worker thread."""
                    future = asyncio.run_coroutine_threadsafe(
                        _ask(websocket, step), loop
                    )
                    return future.result()

                result = await asyncio.to_thread(
                    orchestrator.handle, message.strip(), confirm
                )
                await websocket.send_json(
                    {
                        "type": "reply",
                        "reply": result.reply,
                        "agent": result.agent.name if result.agent else None,
                        "session_id": session_id,
                        "steps": [s.model_dump() for s in _to_steps(result)],
                    }
                )
        except WebSocketDisconnect:
            return

    return app


async def _ask(websocket: WebSocket, step: PlanStep) -> bool:
    """Send an approval request and wait for the client's yes/no."""
    await websocket.send_json(
        {
            "type": "approval_request",
            "tool": step.tool,
            "arguments": step.arguments,
            "rationale": step.rationale,
        }
    )
    answer = await websocket.receive_json()
    return bool(answer.get("approve", False))
