"""Entry point that serves the NOVA API."""

from __future__ import annotations

import os
from pathlib import Path

import uvicorn

from nova.api.app import create_app
from nova.audit import AuditLog
from nova.cli import build_orchestrator
from nova.config import NovaConfig
from nova.memory.store import MemoryStore
from nova.plugins import load_plugins
from nova.tools.builtin import build_default_registry


def build_app(config: NovaConfig):
    """Create the FastAPI app for `config`."""
    memory = MemoryStore(config.memory_db_path)
    return create_app(
        config=config,
        orchestrator_factory=lambda: build_orchestrator(config),
        memory=memory,
    )


def main() -> int:
    config = NovaConfig.from_env(os.environ, default_root=Path.cwd() / "workspace")

    # Surface plugin discovery once at startup so failures are visible.
    result = load_plugins(build_default_registry(), AuditLog(config.audit_log_path))
    if result.loaded:
        print(f"Plugins loaded: {', '.join(sorted(result.loaded))}")
    for name, reason in result.failed.items():
        print(f"Plugin {name!r} failed to load: {reason}")

    print(f"Workspace: {config.workspace_root}")
    print(f"API key:   {config.api_key}")
    print(f"Listening: http://{config.api_host}:{config.api_port}")
    print("Send it as the X-API-Key header.")

    uvicorn.run(build_app(config), host=config.api_host, port=config.api_port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
