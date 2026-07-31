import sys

import pytest

from nova.audit import AuditLog
from nova.config import NovaConfig
from nova.memory.store import MemoryStore
from nova.platform import get_adapter
from nova.tools.base import ToolContext

# Commands that mean the same thing in PowerShell and in bash. Any test that
# runs a real subprocess MUST pull its command from here so the suite passes
# unchanged on Windows, macOS and Linux.
_SNIPPETS = {
    "win32": {
        "echo": "Write-Output 'hello nova'",
        "cwd": "(Get-Location).Path",
        "fail": "exit 3",
        "sleep": "Start-Sleep -Seconds 10",
    },
    "posix": {
        "echo": "echo 'hello nova'",
        "cwd": "pwd",
        "fail": "exit 3",
        "sleep": "sleep 10",
    },
}


@pytest.fixture
def shell_snippets():
    """Shell commands for the host platform, keyed by intent."""
    return _SNIPPETS["win32"] if sys.platform == "win32" else _SNIPPETS["posix"]


@pytest.fixture
def tool_context(tmp_path):
    """A ToolContext rooted at an isolated temporary workspace."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    config = NovaConfig.from_env(
        {"NOVA_WORKSPACE_ROOT": str(workspace), "NOVA_SHELL_TIMEOUT_SECONDS": "20"},
        default_root=workspace,
    )
    memory = MemoryStore(config.memory_db_path)
    try:
        yield ToolContext(
            config=config,
            adapter=get_adapter(),
            audit=AuditLog(config.audit_log_path),
            memory=memory,
        )
    finally:
        memory.close()
