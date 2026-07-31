"""Runtime configuration for NOVA."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_AUDIT_FILENAME = "nova-audit.jsonl"
DEFAULT_MEMORY_FILENAME = "nova-memory.db"
DEFAULT_LLM_PROVIDER = "anthropic"
DEFAULT_LLM_MODEL = "claude-opus-5"
DEFAULT_SHELL_TIMEOUT_SECONDS = 30
DEFAULT_MAX_PLAN_STEPS = 8


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
        )
