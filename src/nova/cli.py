"""Text chat interface for NOVA."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path

from nova.agents.router import AgentRouter
from nova.audit import AuditLog
from nova.config import NovaConfig
from nova.llm import get_provider
from nova.memory.store import MemoryStore
from nova.orchestrator import ConfirmCallback, Orchestrator
from nova.permissions import DEFAULT_POLICY, PermissionEngine
from nova.planner import Planner, PlanStep
from nova.platform import get_adapter
from nova.tools.base import ToolContext
from nova.tools.builtin import build_default_registry

EXIT_COMMANDS = {"/exit", "/quit"}

InputFn = Callable[[str], str]
OutputFn = Callable[[str], None]


def build_orchestrator(config: NovaConfig) -> Orchestrator:
    """Wire every component together from configuration."""
    registry = build_default_registry()
    audit = AuditLog(config.audit_log_path)
    provider = get_provider(config)
    memory = MemoryStore(config.memory_db_path)
    context = ToolContext(
        config=config, adapter=get_adapter(), audit=audit, memory=memory
    )
    return Orchestrator(
        planner=Planner(
            provider=provider,
            registry=registry,
            max_steps=config.max_plan_steps,
            memory=memory,
        ),
        registry=registry,
        permissions=PermissionEngine(DEFAULT_POLICY, audit),
        provider=provider,
        context=context,
        router=AgentRouter(provider=provider, audit=audit),
    )


def make_confirmer(input_fn: InputFn, output_fn: OutputFn) -> ConfirmCallback:
    """Build a confirmation callback backed by the terminal."""

    def confirm(step: PlanStep) -> bool:
        output_fn(f"\n  NOVA wants to run: {step.tool} {step.arguments}")
        output_fn(f"  Reason: {step.rationale}")
        try:
            answer = input_fn("  Allow? [y/N] ")
        except EOFError:
            return False
        return answer.strip().lower() in {"y", "yes"}

    return confirm


def run_repl(orchestrator: Orchestrator, input_fn: InputFn, output_fn: OutputFn) -> None:
    """Read user messages until EOF or an exit command."""
    confirm = make_confirmer(input_fn, output_fn)
    output_fn("NOVA ready. Type /exit to quit.")

    while True:
        try:
            message = input_fn("\nyou> ")
        except EOFError:
            break

        stripped = message.strip()
        if not stripped:
            continue
        if stripped.lower() in EXIT_COMMANDS:
            break

        result = orchestrator.handle(stripped, confirm)
        output_fn(f"\nnova> {result.reply}")

    output_fn("\nGoodbye.")


def main() -> int:
    """Console-script entry point."""
    config = NovaConfig.from_env(os.environ, default_root=Path.cwd() / "workspace")
    print(f"Workspace: {config.workspace_root}")
    print(f"Audit log: {config.audit_log_path}")
    run_repl(build_orchestrator(config), input, lambda text: print(text))
    return 0


if __name__ == "__main__":
    sys.exit(main())
