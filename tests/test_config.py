from pathlib import Path

from nova.config import NovaConfig


def test_from_env_uses_defaults_when_env_is_empty(tmp_path):
    config = NovaConfig.from_env({}, default_root=tmp_path)

    assert config.workspace_root == tmp_path.resolve()
    assert config.audit_log_path == (tmp_path / "nova-audit.jsonl").resolve()
    assert config.memory_db_path == (tmp_path / "nova-memory.db").resolve()
    assert config.llm_provider == "anthropic"
    assert config.llm_model == "claude-opus-5"
    assert config.shell_timeout_seconds == 30
    assert config.max_plan_steps == 8


def test_from_env_overrides_from_environment(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    env = {
        "NOVA_WORKSPACE_ROOT": str(workspace),
        "NOVA_LLM_PROVIDER": "fake",
        "NOVA_LLM_MODEL": "test-model",
        "NOVA_SHELL_TIMEOUT_SECONDS": "5",
        "NOVA_MAX_PLAN_STEPS": "3",
    }

    config = NovaConfig.from_env(env, default_root=tmp_path)

    assert config.workspace_root == workspace.resolve()
    assert config.llm_provider == "fake"
    assert config.llm_model == "test-model"
    assert config.shell_timeout_seconds == 5
    assert config.max_plan_steps == 3


def test_workspace_root_is_created_if_missing(tmp_path):
    target = tmp_path / "brand-new"

    config = NovaConfig.from_env({"NOVA_WORKSPACE_ROOT": str(target)}, default_root=tmp_path)

    assert config.workspace_root.is_dir()
    assert isinstance(config.workspace_root, Path)
