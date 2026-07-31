"""Runtime configuration for NOVA."""

from __future__ import annotations

import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_AUDIT_FILENAME = "nova-audit.jsonl"
DEFAULT_MEMORY_FILENAME = "nova-memory.db"
DEFAULT_LLM_PROVIDER = "anthropic"
DEFAULT_LLM_MODEL = "claude-opus-5"
DEFAULT_SHELL_TIMEOUT_SECONDS = 30
DEFAULT_MAX_PLAN_STEPS = 8
DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8765
API_KEY_FILENAME = ".nova-api-key"


@dataclass(frozen=True)
class NovaConfig:
    """Immutable settings shared by every NOVA component."""

    workspace_root: Path
    audit_log_path: Path
    memory_db_path: Path
    llm_provider: str
    llm_model: str
    shell_timeout_seconds: int
    max_plan_steps: int
    api_key: str
    api_host: str
    api_port: int

    @classmethod
    def from_env(cls, env: Mapping[str, str], default_root: Path) -> "NovaConfig":
        root = Path(env.get("NOVA_WORKSPACE_ROOT", str(default_root)))
        root.mkdir(parents=True, exist_ok=True)
        root = root.resolve()

        audit_path = Path(
            env.get("NOVA_AUDIT_LOG_PATH", str(root / DEFAULT_AUDIT_FILENAME))
        ).resolve()

        memory_path = Path(
            env.get("NOVA_MEMORY_DB_PATH", str(root / DEFAULT_MEMORY_FILENAME))
        ).resolve()

        return cls(
            workspace_root=root,
            audit_log_path=audit_path,
            memory_db_path=memory_path,
            llm_provider=env.get("NOVA_LLM_PROVIDER", DEFAULT_LLM_PROVIDER),
            llm_model=env.get("NOVA_LLM_MODEL", DEFAULT_LLM_MODEL),
            shell_timeout_seconds=int(
                env.get("NOVA_SHELL_TIMEOUT_SECONDS", str(DEFAULT_SHELL_TIMEOUT_SECONDS))
            ),
            max_plan_steps=int(
                env.get("NOVA_MAX_PLAN_STEPS", str(DEFAULT_MAX_PLAN_STEPS))
            ),
            api_key=env.get("NOVA_API_KEY") or _load_or_create_api_key(root),
            api_host=env.get("NOVA_API_HOST", DEFAULT_API_HOST),
            api_port=int(env.get("NOVA_API_PORT", str(DEFAULT_API_PORT))),
        )


def _load_or_create_api_key(root: Path) -> str:
    """Return the workspace's API key, generating and persisting one if absent.

    Bound to the workspace rather than regenerated per start, so a client that
    paired once keeps working across restarts.
    """
    key_path = root / API_KEY_FILENAME
    if key_path.is_file():
        existing = key_path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    key = secrets.token_urlsafe(32)
    key_path.write_text(key, encoding="utf-8")
    return key
