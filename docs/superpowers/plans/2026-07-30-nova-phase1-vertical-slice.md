# Project NOVA — Phase 1 Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working local AI assistant that turns a natural-language message into a permission-gated, audited sequence of tool calls against the filesystem and shell, and reports the result back in natural language — running natively on Windows, macOS and Linux.

**Architecture:** A pure-Python core with a swappable `PlatformAdapter` (Windows via PowerShell, macOS and Linux via bash) and a swappable `LLMProvider` (Anthropic implemented, plus a scripted fake so every test runs offline). Capabilities are `ToolSpec` objects in a single `ToolRegistry`; the registry is the one source of truth, consumed in-process by the orchestrator and re-exported over a real MCP stdio server so third parties get the same tools. Every turn walks the PRD §11 pipeline — plan → permission check → execute → verify → respond — and every decision and execution is appended to a JSONL audit log.

**Tech Stack:** Python 3.11, pytest, `anthropic` SDK, `mcp` SDK, PowerShell / bash (via `subprocess`), setuptools/pyproject, git.

## Global Constraints

- **Python version:** 3.11 exactly. Create the venv with `py -3.11 -m venv .venv`. Do not use 3.10 (missing `typing.Self` / `StrEnum` usage) or 3.14 (dependency wheels unavailable).
- **Always invoke Python through the venv explicitly:** `.venv\Scripts\python.exe -m <module>`. Never rely on an activated venv; never call bare `python`.
- **Repo root** is `C:\Users\Abhishek\Desktop\OS`. All commands in this plan run from the repo root.
- **Shell for commands in this plan** is PowerShell (Windows PowerShell 5.1). `&&` and `||` do not work — use `;` or separate commands. On macOS/Linux the equivalent is `.venv/bin/python -m ...`.
- **Tri-platform desktop is a hard requirement.** Windows, macOS (Apple Silicon) and Linux must all be supported. No OS-specific call may appear outside `src/nova/platform/`. Any test that runs a real subprocess must select its command via the `shell_snippets` fixture, never hardcode PowerShell or bash syntax.
- **Layout is `src/`-based.** Package code lives in `src/nova/`, tests in `tests/`. Never place a `nova/` directory at the repo root.
- **No network in tests.** Every test must pass with no API key set and no internet. The Anthropic provider is only ever tested with an injected fake client.
- **Every tool execution and every permission decision is written to the audit log.** A code path that executes a tool without an audit record is a defect.
- **All filesystem tool access is confined to `workspace_root`.** Any path resolving outside it raises `PathOutsideWorkspaceError`. This is the security boundary — never bypass it "just for a test".
- **Model ID** for the Anthropic provider is `claude-opus-5`.
- **TDD is mandatory:** write the failing test, watch it fail, write the minimal implementation, watch it pass, commit.

## Out of Scope for This Plan

These PRD sections are deliberately deferred to follow-on plans, one per subsystem: voice pipeline (§13), mobile companion (§7B), cloud gateway (§7C), multi-agent orchestration beyond a single planner (§8), long-term/knowledge/workflow memory (§9), browser/Docker/Git/email/calendar/PDF/OCR tools (§10), plugin marketplace (§16), REST/WebSocket APIs (§17), commercialization (§20). This plan builds the spine those all attach to.

---

## File Structure

| Path | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, dependencies, pytest config, `nova` console script |
| `src/nova/__init__.py` | Package marker, version |
| `src/nova/config.py` | `NovaConfig` dataclass + environment loading |
| `src/nova/audit.py` | Append-only JSONL audit log (`AuditEvent`, `AuditLog`) |
| `src/nova/platform/base.py` | `PlatformAdapter` protocol, shared `resolve_in_workspace()`, `PathOutsideWorkspaceError`, `UnsupportedPlatformError` |
| `src/nova/platform/windows.py` | `WindowsAdapter` — PowerShell argv |
| `src/nova/platform/posix.py` | `MacOSAdapter`, `LinuxAdapter` — bash argv |
| `src/nova/platform/__init__.py` | `get_adapter()` platform dispatch (win32 / darwin / linux) |
| `src/nova/tools/base.py` | `Risk`, `ToolResult`, `ToolSpec`, `ToolContext` |
| `src/nova/tools/registry.py` | `ToolRegistry` — register/get/list, MCP schema export |
| `src/nova/tools/files.py` | `file_read`, `file_write`, `file_list` tools |
| `src/nova/tools/shell.py` | `shell_run` tool |
| `src/nova/tools/builtin.py` | `build_default_registry()` — wires all tools together |
| `src/nova/permissions.py` | `Decision`, `PolicyRule`, `PermissionEngine`, destructive-command denylist |
| `src/nova/llm/base.py` | `Message`, `LLMProvider` protocol |
| `src/nova/llm/fake.py` | `ScriptedProvider` for deterministic tests |
| `src/nova/llm/anthropic_provider.py` | `AnthropicProvider` wrapping the Anthropic SDK |
| `src/nova/llm/__init__.py` | `get_provider()` dispatch |
| `src/nova/planner.py` | `PlanStep`, `Plan`, `Planner`, `PlanParseError` |
| `src/nova/orchestrator.py` | `StepOutcome`, `TurnResult`, `Orchestrator` — the §11 pipeline |
| `src/nova/cli.py` | `run_repl()` and `main()` — the chat interface |
| `src/nova/mcp_server.py` | MCP stdio server re-exporting the registry |
| `tests/` | Mirrors the above, one test module per source module |

---

### Task 1: Project scaffold and configuration

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/nova/__init__.py`
- Create: `src/nova/config.py`
- Create: `tests/__init__.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `NovaConfig` frozen dataclass with fields `workspace_root: Path`, `audit_log_path: Path`, `llm_provider: str`, `llm_model: str`, `shell_timeout_seconds: int`, `max_plan_steps: int`; and `NovaConfig.from_env(env: Mapping[str, str], default_root: Path) -> NovaConfig`. Every later task receives config through this type.

- [x] **Step 1: Initialize the repository and working branch**

```powershell
git init
git commit --allow-empty -m "chore: initialize repository"
git checkout -b feat/nova-phase1-slice
```

- [x] **Step 2: Create the virtual environment**

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
```

Expected: `Successfully installed pip-...`

- [x] **Step 3: Write `.gitignore`**

```gitignore
.venv/
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.coverage
htmlcov/
nova-audit.jsonl
workspace/
.env
```

- [x] **Step 4: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "nova"
version = "0.1.0"
description = "Project NOVA - personal AI operating system core"
requires-python = ">=3.11,<3.12"
dependencies = [
    "anthropic>=0.40",
    "mcp>=2.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
nova = "nova.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
```

- [x] **Step 5: Create package markers**

`src/nova/__init__.py`:

```python
"""Project NOVA - personal AI operating system core."""

__version__ = "0.1.0"
```

`tests/__init__.py`: create as an empty file.

- [x] **Step 6: Install the package in editable mode with dev extras**

```powershell
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

Expected: ends with `Successfully installed ... nova-0.1.0 ...`

- [x] **Step 7: Write the failing test**

`tests/test_config.py`:

```python
from pathlib import Path

from nova.config import NovaConfig


def test_from_env_uses_defaults_when_env_is_empty(tmp_path):
    config = NovaConfig.from_env({}, default_root=tmp_path)

    assert config.workspace_root == tmp_path.resolve()
    assert config.audit_log_path == (tmp_path / "nova-audit.jsonl").resolve()
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
```

- [x] **Step 8: Run the test to verify it fails**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'nova.config'`

- [x] **Step 9: Write the minimal implementation**

`src/nova/config.py`:

```python
"""Runtime configuration for NOVA."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

DEFAULT_AUDIT_FILENAME = "nova-audit.jsonl"
DEFAULT_LLM_PROVIDER = "anthropic"
DEFAULT_LLM_MODEL = "claude-opus-5"
DEFAULT_SHELL_TIMEOUT_SECONDS = 30
DEFAULT_MAX_PLAN_STEPS = 8


@dataclass(frozen=True)
class NovaConfig:
    """Immutable settings shared by every NOVA component."""

    workspace_root: Path
    audit_log_path: Path
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

        return cls(
            workspace_root=root,
            audit_log_path=audit_path,
            llm_provider=env.get("NOVA_LLM_PROVIDER", DEFAULT_LLM_PROVIDER),
            llm_model=env.get("NOVA_LLM_MODEL", DEFAULT_LLM_MODEL),
            shell_timeout_seconds=int(
                env.get("NOVA_SHELL_TIMEOUT_SECONDS", str(DEFAULT_SHELL_TIMEOUT_SECONDS))
            ),
            max_plan_steps=int(
                env.get("NOVA_MAX_PLAN_STEPS", str(DEFAULT_MAX_PLAN_STEPS))
            ),
        )
```

- [x] **Step 10: Run the test to verify it passes**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_config.py -v
```

Expected: PASS — `3 passed`

- [x] **Step 11: Commit**

```powershell
git add .gitignore pyproject.toml src tests
git commit -m "feat: scaffold nova package with environment-driven config"
```

---

### Task 2: Append-only audit log

**Files:**
- Create: `src/nova/audit.py`
- Test: `tests/test_audit.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `AuditEvent` frozen dataclass with fields `event_id: str`, `timestamp: str`, `event_type: str`, `payload: dict`; and `AuditLog` with `__init__(self, path: Path)`, `record(self, event_type: str, payload: dict) -> AuditEvent`, `read_all(self) -> list[AuditEvent]`. Tasks 5, 6, 7 and 10 all call `record`.

- [x] **Step 1: Write the failing test**

`tests/test_audit.py`:

```python
import json

from nova.audit import AuditEvent, AuditLog


def test_record_appends_one_json_line(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")

    event = log.record("tool_executed", {"tool": "file_read", "ok": True})

    lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    stored = json.loads(lines[0])
    assert stored["event_type"] == "tool_executed"
    assert stored["payload"] == {"tool": "file_read", "ok": True}
    assert stored["event_id"] == event.event_id


def test_record_creates_parent_directories(tmp_path):
    log = AuditLog(tmp_path / "nested" / "deeper" / "audit.jsonl")

    log.record("started", {})

    assert (tmp_path / "nested" / "deeper" / "audit.jsonl").is_file()


def test_read_all_returns_events_in_write_order(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    log.record("first", {"n": 1})
    log.record("second", {"n": 2})

    events = log.read_all()

    assert [e.event_type for e in events] == ["first", "second"]
    assert all(isinstance(e, AuditEvent) for e in events)


def test_event_ids_are_unique(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")

    ids = {log.record("tick", {}).event_id for _ in range(50)}

    assert len(ids) == 50


def test_timestamp_is_utc_iso8601(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")

    event = log.record("tick", {})

    assert event.timestamp.endswith("+00:00")
```

- [x] **Step 2: Run the test to verify it fails**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_audit.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'nova.audit'`

- [x] **Step 3: Write the minimal implementation**

`src/nova/audit.py`:

```python
"""Append-only audit trail for every NOVA decision and execution."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class AuditEvent:
    """One immutable record of something NOVA decided or did."""

    event_id: str
    timestamp: str
    event_type: str
    payload: dict = field(default_factory=dict)


class AuditLog:
    """Writes AuditEvents as JSON Lines. Never rewrites or truncates."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def record(self, event_type: str, payload: dict) -> AuditEvent:
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            payload=payload,
        )
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), default=str) + "\n")
        return event

    def read_all(self) -> list[AuditEvent]:
        if not self._path.is_file():
            return []
        events: list[AuditEvent] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            events.append(AuditEvent(**json.loads(line)))
        return events
```

- [x] **Step 4: Run the test to verify it passes**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_audit.py -v
```

Expected: PASS — `5 passed`

- [x] **Step 5: Commit**

```powershell
git add src/nova/audit.py tests/test_audit.py
git commit -m "feat: add append-only JSONL audit log"
```

---

### Task 3: Cross-platform adapters with workspace containment

**Files:**
- Create: `src/nova/platform/__init__.py`
- Create: `src/nova/platform/base.py`
- Create: `src/nova/platform/windows.py`
- Create: `src/nova/platform/posix.py`
- Test: `tests/test_platform.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `PathOutsideWorkspaceError(Exception)` and `UnsupportedPlatformError(Exception)` in `nova.platform.base`.
  - Module-level `resolve_in_workspace(workspace_root: Path, relative: str) -> Path` in `nova.platform.base` — the single containment implementation every adapter shares.
  - `PlatformAdapter` protocol with attribute `name: str` and methods `resolve_in_workspace(self, workspace_root: Path, relative: str) -> Path` and `shell_command(self, command: str) -> list[str]`.
  - `BaseAdapter` concrete base supplying `resolve_in_workspace`.
  - `WindowsAdapter` (`name == "windows"`), `MacOSAdapter` (`name == "macos"`), `LinuxAdapter` (`name == "linux"`).
  - `get_adapter(platform_name: str | None = None) -> PlatformAdapter` in `nova.platform`.

  Tasks 5, 6, 11 and 12 call `resolve_in_workspace`, `shell_command` and `get_adapter`.

**Design note:** containment logic is identical on every OS — it is pure `pathlib` — so it lives in one function and the adapters differ only in how they spell "run this command in a shell". This is why the whole tri-platform surface is unit-testable from any one machine.

- [x] **Step 1: Write the failing test**

`tests/test_platform.py`:

```python
import pytest

from nova.platform import get_adapter
from nova.platform.base import (
    PathOutsideWorkspaceError,
    PlatformAdapter,
    UnsupportedPlatformError,
)
from nova.platform.posix import LinuxAdapter, MacOSAdapter
from nova.platform.windows import WindowsAdapter

ADAPTERS = [WindowsAdapter(), MacOSAdapter(), LinuxAdapter()]


@pytest.mark.parametrize(
    "adapter,expected",
    [(WindowsAdapter(), "windows"), (MacOSAdapter(), "macos"), (LinuxAdapter(), "linux")],
)
def test_adapter_reports_its_name(adapter, expected):
    assert adapter.name == expected


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_every_adapter_satisfies_the_protocol(adapter):
    assert isinstance(adapter, PlatformAdapter)


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_resolve_returns_path_inside_workspace(adapter, tmp_path):
    resolved = adapter.resolve_in_workspace(tmp_path, "notes/todo.txt")

    assert resolved == (tmp_path / "notes" / "todo.txt").resolve()


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_resolve_allows_the_root_itself(adapter, tmp_path):
    assert adapter.resolve_in_workspace(tmp_path, ".") == tmp_path.resolve()


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_resolve_rejects_parent_traversal(adapter, tmp_path):
    with pytest.raises(PathOutsideWorkspaceError):
        adapter.resolve_in_workspace(tmp_path, "../escaped.txt")


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_resolve_rejects_nested_parent_traversal(adapter, tmp_path):
    with pytest.raises(PathOutsideWorkspaceError):
        adapter.resolve_in_workspace(tmp_path, "a/b/../../../escaped.txt")


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_resolve_rejects_absolute_paths_outside_workspace(adapter, tmp_path):
    outside = str(tmp_path.parent / "escaped.txt")

    with pytest.raises(PathOutsideWorkspaceError):
        adapter.resolve_in_workspace(tmp_path, outside)


def test_windows_shell_command_builds_non_interactive_powershell_argv():
    assert WindowsAdapter().shell_command("Get-Date") == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        "Get-Date",
    ]


def test_macos_shell_command_builds_bash_argv():
    assert MacOSAdapter().shell_command("date") == ["/bin/bash", "-c", "date"]


def test_linux_shell_command_builds_bash_argv():
    assert LinuxAdapter().shell_command("date") == ["/bin/bash", "-c", "date"]


def test_get_adapter_returns_windows_adapter_for_win32():
    assert isinstance(get_adapter("win32"), WindowsAdapter)


def test_get_adapter_returns_macos_adapter_for_darwin():
    assert isinstance(get_adapter("darwin"), MacOSAdapter)


def test_get_adapter_returns_linux_adapter_for_linux():
    assert isinstance(get_adapter("linux"), LinuxAdapter)


def test_get_adapter_rejects_unknown_platforms():
    with pytest.raises(UnsupportedPlatformError):
        get_adapter("plan9")
```

- [x] **Step 2: Run the test to verify it fails**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_platform.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'nova.platform'`

- [x] **Step 3: Write the platform interface and shared containment**

`src/nova/platform/base.py`:

```python
"""Operating-system abstraction shared by all NOVA tools."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


class PathOutsideWorkspaceError(Exception):
    """Raised when a requested path escapes the configured workspace root."""


class UnsupportedPlatformError(Exception):
    """Raised when no adapter exists for the current operating system."""


def resolve_in_workspace(workspace_root: Path, relative: str) -> Path:
    """Resolve `relative` against `workspace_root`, refusing to escape it.

    Pure pathlib, so it behaves identically on every platform and can be
    exercised from any one of them.
    """
    root = Path(workspace_root).resolve()
    candidate = Path(root, relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise PathOutsideWorkspaceError(
            f"{candidate} is outside the workspace root {root}"
        )
    return candidate


@runtime_checkable
class PlatformAdapter(Protocol):
    """Everything NOVA needs to know about the host operating system."""

    name: str

    def resolve_in_workspace(self, workspace_root: Path, relative: str) -> Path:
        """Resolve `relative` against the workspace, refusing to escape it."""

    def shell_command(self, command: str) -> list[str]:
        """Return the argv that runs `command` in this platform's shell."""


class BaseAdapter:
    """Shared behaviour. Subclasses supply `name` and `shell_command`."""

    name: str = ""

    def resolve_in_workspace(self, workspace_root: Path, relative: str) -> Path:
        return resolve_in_workspace(workspace_root, relative)

    def shell_command(self, command: str) -> list[str]:
        raise NotImplementedError
```

- [x] **Step 4: Write the Windows adapter**

`src/nova/platform/windows.py`:

```python
"""Windows implementation of the platform adapter."""

from __future__ import annotations

from nova.platform.base import BaseAdapter


class WindowsAdapter(BaseAdapter):
    """PowerShell invocation for Windows hosts."""

    name = "windows"

    def shell_command(self, command: str) -> list[str]:
        return [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ]
```

- [x] **Step 5: Write the macOS and Linux adapters**

`src/nova/platform/posix.py`:

```python
"""macOS and Linux implementations of the platform adapter."""

from __future__ import annotations

from nova.platform.base import BaseAdapter

BASH = "/bin/bash"


class PosixAdapter(BaseAdapter):
    """Shared POSIX behaviour.

    bash is used rather than the user's login shell so that command semantics
    are identical on macOS (where the default is zsh) and Linux. `-c` rather
    than `-lc` keeps startup fast and avoids inheriting profile side effects.
    """

    def shell_command(self, command: str) -> list[str]:
        return [BASH, "-c", command]


class MacOSAdapter(PosixAdapter):
    """Apple Silicon and Intel macOS hosts."""

    name = "macos"


class LinuxAdapter(PosixAdapter):
    """Linux hosts."""

    name = "linux"
```

- [x] **Step 6: Write the platform dispatcher**

`src/nova/platform/__init__.py`:

```python
"""Platform adapter selection."""

from __future__ import annotations

import sys

from nova.platform.base import (
    BaseAdapter,
    PathOutsideWorkspaceError,
    PlatformAdapter,
    UnsupportedPlatformError,
    resolve_in_workspace,
)
from nova.platform.posix import LinuxAdapter, MacOSAdapter, PosixAdapter
from nova.platform.windows import WindowsAdapter

__all__ = [
    "BaseAdapter",
    "LinuxAdapter",
    "MacOSAdapter",
    "PathOutsideWorkspaceError",
    "PlatformAdapter",
    "PosixAdapter",
    "UnsupportedPlatformError",
    "WindowsAdapter",
    "get_adapter",
    "resolve_in_workspace",
]

_ADAPTERS = {
    "win32": WindowsAdapter,
    "darwin": MacOSAdapter,
    "linux": LinuxAdapter,
}


def get_adapter(platform_name: str | None = None) -> PlatformAdapter:
    """Return the adapter for `platform_name` (defaults to the running host)."""
    name = platform_name if platform_name is not None else sys.platform
    try:
        return _ADAPTERS[name]()
    except KeyError:
        raise UnsupportedPlatformError(
            f"no NOVA platform adapter for {name!r}; supported: {sorted(_ADAPTERS)}"
        ) from None
```

- [x] **Step 7: Run the test to verify it passes**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_platform.py -v
```

Expected: PASS — `28 passed`

- [x] **Step 8: Commit**

```powershell
git add src/nova/platform tests/test_platform.py
git commit -m "feat: add Windows, macOS and Linux adapters with shared path containment"
```

---

### Task 4: Tool registry

**Files:**
- Create: `src/nova/tools/__init__.py`
- Create: `src/nova/tools/base.py`
- Create: `src/nova/tools/registry.py`
- Test: `tests/test_tool_registry.py`

**Interfaces:**
- Consumes: `NovaConfig` (Task 1), `AuditLog` (Task 2), `PlatformAdapter` (Task 3).
- Produces:
  - `Risk(StrEnum)` with members `READ = "read"`, `WRITE = "write"`, `EXECUTE = "execute"`.
  - `ToolResult` frozen dataclass: `ok: bool`, `output: str`, `error: str | None = None`.
  - `ToolContext` frozen dataclass: `config: NovaConfig`, `adapter: PlatformAdapter`, `audit: AuditLog`.
  - `ToolSpec` frozen dataclass: `name: str`, `description: str`, `input_schema: dict`, `risk: Risk`, `handler: Callable[[dict, ToolContext], ToolResult]`.
  - `ToolRegistry` with `register(spec) -> None`, `get(name) -> ToolSpec`, `list_specs() -> list[ToolSpec]`, `to_mcp_tools() -> list[dict]`, `describe_for_prompt() -> str`.
  - `UnknownToolError(Exception)` and `DuplicateToolError(Exception)`.

  Tasks 5, 6, 7, 9, 10 and 12 all depend on these names.

- [x] **Step 1: Write the failing test**

`tests/test_tool_registry.py`:

```python
import pytest

from nova.tools.base import Risk, ToolResult, ToolSpec
from nova.tools.registry import DuplicateToolError, ToolRegistry, UnknownToolError


def _spec(name: str = "echo", risk: Risk = Risk.READ) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=f"{name} description",
        input_schema={
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        risk=risk,
        handler=lambda arguments, context: ToolResult(ok=True, output=arguments["text"]),
    )


def test_register_then_get_returns_the_same_spec():
    registry = ToolRegistry()
    spec = _spec()

    registry.register(spec)

    assert registry.get("echo") is spec


def test_get_unknown_tool_raises():
    registry = ToolRegistry()

    with pytest.raises(UnknownToolError):
        registry.get("nope")


def test_registering_the_same_name_twice_raises():
    registry = ToolRegistry()
    registry.register(_spec())

    with pytest.raises(DuplicateToolError):
        registry.register(_spec())


def test_list_specs_is_sorted_by_name():
    registry = ToolRegistry()
    registry.register(_spec("zeta"))
    registry.register(_spec("alpha"))

    assert [s.name for s in registry.list_specs()] == ["alpha", "zeta"]


def test_to_mcp_tools_emits_mcp_shaped_dicts():
    registry = ToolRegistry()
    registry.register(_spec())

    tools = registry.to_mcp_tools()

    assert tools == [
        {
            "name": "echo",
            "description": "echo description",
            "inputSchema": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        }
    ]


def test_describe_for_prompt_lists_name_risk_and_schema():
    registry = ToolRegistry()
    registry.register(_spec("shell_run", Risk.EXECUTE))

    description = registry.describe_for_prompt()

    assert "shell_run" in description
    assert "execute" in description
    assert "text" in description


def test_risk_values_are_stable_strings():
    assert Risk.READ == "read"
    assert Risk.WRITE == "write"
    assert Risk.EXECUTE == "execute"
```

- [x] **Step 2: Run the test to verify it fails**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_tool_registry.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'nova.tools'`

- [x] **Step 3: Write the tool primitives**

`src/nova/tools/__init__.py`: create as an empty file.

`src/nova/tools/base.py`:

```python
"""Core types every NOVA tool is built from."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from nova.audit import AuditLog
from nova.config import NovaConfig
from nova.platform.base import PlatformAdapter


class Risk(StrEnum):
    """How dangerous a tool is, which drives the permission policy."""

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"


@dataclass(frozen=True)
class ToolResult:
    """Outcome of a single tool invocation."""

    ok: bool
    output: str
    error: str | None = None


@dataclass(frozen=True)
class ToolContext:
    """Everything a tool handler is allowed to reach out to."""

    config: NovaConfig
    adapter: PlatformAdapter
    audit: AuditLog


@dataclass(frozen=True)
class ToolSpec:
    """A capability, described the way MCP describes tools."""

    name: str
    description: str
    input_schema: dict
    risk: Risk
    handler: Callable[[dict, ToolContext], ToolResult]
```

- [x] **Step 4: Write the registry**

`src/nova/tools/registry.py`:

```python
"""The single source of truth for what NOVA can do."""

from __future__ import annotations

import json

from nova.tools.base import ToolSpec


class UnknownToolError(Exception):
    """Raised when a plan references a tool that is not registered."""


class DuplicateToolError(Exception):
    """Raised when two tools claim the same name."""


class ToolRegistry:
    """Holds ToolSpecs and renders them for the LLM and for MCP clients."""

    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._specs:
            raise DuplicateToolError(f"tool {spec.name!r} is already registered")
        self._specs[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        try:
            return self._specs[name]
        except KeyError:
            raise UnknownToolError(f"no tool named {name!r}") from None

    def list_specs(self) -> list[ToolSpec]:
        return [self._specs[name] for name in sorted(self._specs)]

    def to_mcp_tools(self) -> list[dict]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "inputSchema": spec.input_schema,
            }
            for spec in self.list_specs()
        ]

    def describe_for_prompt(self) -> str:
        lines = []
        for spec in self.list_specs():
            lines.append(
                f"- {spec.name} (risk: {spec.risk.value}): {spec.description}\n"
                f"  arguments schema: {json.dumps(spec.input_schema)}"
            )
        return "\n".join(lines)
```

- [x] **Step 5: Run the test to verify it passes**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_tool_registry.py -v
```

Expected: PASS — `7 passed`

- [x] **Step 6: Commit**

```powershell
git add src/nova/tools tests/test_tool_registry.py
git commit -m "feat: add tool registry with MCP-shaped schema export"
```

---

### Task 5: File tools

**Files:**
- Create: `src/nova/tools/files.py`
- Test: `tests/conftest.py`
- Test: `tests/test_tools_files.py`

**Interfaces:**
- Consumes: `ToolSpec`, `ToolResult`, `ToolContext`, `Risk` (Task 4); `WindowsAdapter` (Task 3); `AuditLog` (Task 2); `NovaConfig` (Task 1).
- Produces: `FILE_READ: ToolSpec`, `FILE_WRITE: ToolSpec`, `FILE_LIST: ToolSpec` (tool names `file_read`, `file_write`, `file_list`), and `FILE_TOOLS: list[ToolSpec]`. Also produces the shared pytest fixture `tool_context` in `tests/conftest.py`, used by Tasks 6, 7 and 10.

- [x] **Step 1: Write the shared test fixture**

`tests/conftest.py`:

```python
import sys

import pytest

from nova.audit import AuditLog
from nova.config import NovaConfig
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
    return ToolContext(
        config=config,
        adapter=get_adapter(),
        audit=AuditLog(config.audit_log_path),
    )
```

- [x] **Step 2: Write the failing test**

`tests/test_tools_files.py`:

```python
from nova.tools.base import Risk
from nova.tools.files import FILE_LIST, FILE_READ, FILE_TOOLS, FILE_WRITE


def test_tool_names_and_risks():
    assert FILE_READ.name == "file_read"
    assert FILE_READ.risk is Risk.READ
    assert FILE_WRITE.name == "file_write"
    assert FILE_WRITE.risk is Risk.WRITE
    assert FILE_LIST.name == "file_list"
    assert FILE_LIST.risk is Risk.READ
    assert FILE_TOOLS == [FILE_LIST, FILE_READ, FILE_WRITE]


def test_file_write_then_file_read_round_trips(tool_context):
    write_result = FILE_WRITE.handler(
        {"path": "notes/hello.txt", "content": "hello nova"}, tool_context
    )
    assert write_result.ok is True

    read_result = FILE_READ.handler({"path": "notes/hello.txt"}, tool_context)

    assert read_result.ok is True
    assert read_result.output == "hello nova"


def test_file_write_creates_parent_directories(tool_context):
    FILE_WRITE.handler({"path": "a/b/c/deep.txt", "content": "x"}, tool_context)

    assert (tool_context.config.workspace_root / "a" / "b" / "c" / "deep.txt").is_file()


def test_file_read_missing_file_fails_without_raising(tool_context):
    result = FILE_READ.handler({"path": "absent.txt"}, tool_context)

    assert result.ok is False
    assert "not found" in result.error


def test_file_read_refuses_paths_outside_the_workspace(tool_context):
    result = FILE_READ.handler({"path": "../../secrets.txt"}, tool_context)

    assert result.ok is False
    assert "outside the workspace" in result.error


def test_file_write_refuses_paths_outside_the_workspace(tool_context):
    result = FILE_WRITE.handler({"path": "../evil.txt", "content": "x"}, tool_context)

    assert result.ok is False
    assert "outside the workspace" in result.error
    assert not (tool_context.config.workspace_root.parent / "evil.txt").exists()


def test_file_list_reports_files_and_directories(tool_context):
    FILE_WRITE.handler({"path": "one.txt", "content": "1"}, tool_context)
    FILE_WRITE.handler({"path": "sub/two.txt", "content": "2"}, tool_context)

    result = FILE_LIST.handler({"path": "."}, tool_context)

    assert result.ok is True
    assert "one.txt" in result.output
    assert "sub/" in result.output


def test_file_list_on_missing_directory_fails(tool_context):
    result = FILE_LIST.handler({"path": "nowhere"}, tool_context)

    assert result.ok is False
    assert "not a directory" in result.error


def test_missing_required_argument_fails(tool_context):
    result = FILE_READ.handler({}, tool_context)

    assert result.ok is False
    assert "path" in result.error
```

- [x] **Step 3: Run the test to verify it fails**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_tools_files.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'nova.tools.files'`

- [x] **Step 4: Write the minimal implementation**

`src/nova/tools/files.py`:

```python
"""Filesystem tools, confined to the workspace root."""

from __future__ import annotations

from nova.platform.base import PathOutsideWorkspaceError
from nova.tools.base import Risk, ToolContext, ToolResult, ToolSpec

MAX_READ_CHARS = 20_000


def _require(arguments: dict, key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"argument {key!r} is required and must be a non-empty string")
    return value


def _file_read(arguments: dict, context: ToolContext) -> ToolResult:
    try:
        relative = _require(arguments, "path")
        target = context.adapter.resolve_in_workspace(
            context.config.workspace_root, relative
        )
    except (ValueError, PathOutsideWorkspaceError) as exc:
        return ToolResult(ok=False, output="", error=str(exc))

    if not target.is_file():
        return ToolResult(ok=False, output="", error=f"file not found: {relative}")

    text = target.read_text(encoding="utf-8", errors="replace")
    truncated = text[:MAX_READ_CHARS]
    suffix = "" if len(text) <= MAX_READ_CHARS else "\n... [truncated]"
    return ToolResult(ok=True, output=truncated + suffix)


def _file_write(arguments: dict, context: ToolContext) -> ToolResult:
    try:
        relative = _require(arguments, "path")
        content = arguments.get("content")
        if not isinstance(content, str):
            raise ValueError("argument 'content' is required and must be a string")
        target = context.adapter.resolve_in_workspace(
            context.config.workspace_root, relative
        )
    except (ValueError, PathOutsideWorkspaceError) as exc:
        return ToolResult(ok=False, output="", error=str(exc))

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return ToolResult(ok=True, output=f"wrote {len(content)} characters to {relative}")


def _file_list(arguments: dict, context: ToolContext) -> ToolResult:
    try:
        relative = arguments.get("path", ".")
        if not isinstance(relative, str) or not relative:
            raise ValueError("argument 'path' must be a non-empty string")
        target = context.adapter.resolve_in_workspace(
            context.config.workspace_root, relative
        )
    except (ValueError, PathOutsideWorkspaceError) as exc:
        return ToolResult(ok=False, output="", error=str(exc))

    if not target.is_dir():
        return ToolResult(ok=False, output="", error=f"not a directory: {relative}")

    entries = []
    for child in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        entries.append(f"{child.name}/" if child.is_dir() else child.name)
    return ToolResult(ok=True, output="\n".join(entries) or "(empty)")


FILE_READ = ToolSpec(
    name="file_read",
    description="Read a UTF-8 text file inside the workspace and return its contents.",
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path relative to the workspace root.",
            }
        },
        "required": ["path"],
    },
    risk=Risk.READ,
    handler=_file_read,
)

FILE_WRITE = ToolSpec(
    name="file_write",
    description=(
        "Create or overwrite a UTF-8 text file inside the workspace. "
        "Parent directories are created automatically."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Path relative to the workspace root.",
            },
            "content": {"type": "string", "description": "Full file contents."},
        },
        "required": ["path", "content"],
    },
    risk=Risk.WRITE,
    handler=_file_write,
)

FILE_LIST = ToolSpec(
    name="file_list",
    description="List the entries of a directory inside the workspace.",
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Directory relative to the workspace root. Defaults to '.'.",
            }
        },
        "required": [],
    },
    risk=Risk.READ,
    handler=_file_list,
)

FILE_TOOLS = [FILE_LIST, FILE_READ, FILE_WRITE]
```

- [x] **Step 5: Run the test to verify it passes**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_tools_files.py -v
```

Expected: PASS — `9 passed`

- [x] **Step 6: Commit**

```powershell
git add src/nova/tools/files.py tests/conftest.py tests/test_tools_files.py
git commit -m "feat: add workspace-confined file read/write/list tools"
```

---

### Task 6: Shell tool

**Files:**
- Create: `src/nova/tools/shell.py`
- Create: `src/nova/tools/builtin.py`
- Test: `tests/test_tools_shell.py`

**Interfaces:**
- Consumes: `ToolSpec`, `ToolResult`, `ToolContext`, `Risk` (Task 4); `ToolRegistry` (Task 4); `FILE_TOOLS` (Task 5); `PlatformAdapter.shell_command` (Task 3).
- Produces: `SHELL_RUN: ToolSpec` (tool name `shell_run`), and `build_default_registry() -> ToolRegistry` in `nova.tools.builtin`. Tasks 10, 11 and 12 call `build_default_registry()`.

- [x] **Step 1: Write the failing test**

`tests/test_tools_shell.py`:

```python
from nova.tools.base import Risk
from nova.tools.builtin import build_default_registry
from nova.tools.shell import SHELL_RUN


def test_shell_tool_metadata():
    assert SHELL_RUN.name == "shell_run"
    assert SHELL_RUN.risk is Risk.EXECUTE


def test_shell_run_captures_stdout(tool_context, shell_snippets):
    result = SHELL_RUN.handler({"command": shell_snippets["echo"]}, tool_context)

    assert result.ok is True
    assert "hello nova" in result.output


def test_shell_run_reports_nonzero_exit(tool_context, shell_snippets):
    result = SHELL_RUN.handler({"command": shell_snippets["fail"]}, tool_context)

    assert result.ok is False
    assert "exit code 3" in result.error


def test_shell_run_executes_in_the_workspace_root(tool_context, shell_snippets):
    result = SHELL_RUN.handler({"command": shell_snippets["cwd"]}, tool_context)

    assert result.ok is True
    # macOS reports /private/var/... where tmp_path says /var/..., so compare
    # the resolved leaf rather than the whole string.
    assert tool_context.config.workspace_root.name in result.output


def test_shell_run_times_out(tool_context, shell_snippets):
    from dataclasses import replace

    fast = replace(tool_context, config=replace(tool_context.config, shell_timeout_seconds=1))

    result = SHELL_RUN.handler({"command": shell_snippets["sleep"]}, fast)

    assert result.ok is False
    assert "timed out" in result.error


def test_shell_run_requires_a_command(tool_context):
    result = SHELL_RUN.handler({}, tool_context)

    assert result.ok is False
    assert "command" in result.error


def test_default_registry_contains_every_slice_tool():
    registry = build_default_registry()

    assert [s.name for s in registry.list_specs()] == [
        "file_list",
        "file_read",
        "file_write",
        "shell_run",
    ]
```

- [x] **Step 2: Run the test to verify it fails**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_tools_shell.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'nova.tools.shell'`

- [x] **Step 3: Write the shell tool**

`src/nova/tools/shell.py`:

```python
"""Shell execution tool."""

from __future__ import annotations

import subprocess

from nova.tools.base import Risk, ToolContext, ToolResult, ToolSpec

MAX_OUTPUT_CHARS = 20_000


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + "\n... [truncated]"


def _shell_run(arguments: dict, context: ToolContext) -> ToolResult:
    command = arguments.get("command")
    if not isinstance(command, str) or not command.strip():
        return ToolResult(
            ok=False,
            output="",
            error="argument 'command' is required and must be a non-empty string",
        )

    argv = context.adapter.shell_command(command)
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=context.config.shell_timeout_seconds,
            cwd=context.config.workspace_root,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return ToolResult(
            ok=False,
            output="",
            error=f"timed out after {context.config.shell_timeout_seconds}s",
        )

    stdout = _truncate(completed.stdout.strip())
    stderr = _truncate(completed.stderr.strip())

    if completed.returncode != 0:
        detail = stderr or stdout or "(no output)"
        return ToolResult(
            ok=False,
            output=stdout,
            error=f"exit code {completed.returncode}: {detail}",
        )

    return ToolResult(ok=True, output=stdout or "(no output)")


SHELL_RUN = ToolSpec(
    name="shell_run",
    description=(
        "Run a single PowerShell command with the workspace root as the working "
        "directory and return its output. Use for system inspection and automation."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The PowerShell command to run."}
        },
        "required": ["command"],
    },
    risk=Risk.EXECUTE,
    handler=_shell_run,
)
```

- [x] **Step 4: Write the default registry builder**

`src/nova/tools/builtin.py`:

```python
"""Assembles the tool registry NOVA ships with."""

from __future__ import annotations

from nova.tools.files import FILE_TOOLS
from nova.tools.registry import ToolRegistry
from nova.tools.shell import SHELL_RUN


def build_default_registry() -> ToolRegistry:
    """Return a registry populated with every built-in tool."""
    registry = ToolRegistry()
    for spec in [*FILE_TOOLS, SHELL_RUN]:
        registry.register(spec)
    return registry
```

- [x] **Step 5: Run the test to verify it passes**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_tools_shell.py -v
```

Expected: PASS — `7 passed`

- [x] **Step 6: Commit**

```powershell
git add src/nova/tools/shell.py src/nova/tools/builtin.py tests/test_tools_shell.py
git commit -m "feat: add PowerShell execution tool and default registry"
```

---

### Task 7: Permission engine

**Files:**
- Create: `src/nova/permissions.py`
- Test: `tests/test_permissions.py`

**Interfaces:**
- Consumes: `Risk`, `ToolSpec` (Task 4); `AuditLog` (Task 2).
- Produces:
  - `Decision(StrEnum)` with `ALLOW = "allow"`, `CONFIRM = "confirm"`, `DENY = "deny"`.
  - `PolicyRule` frozen dataclass: `tool: str` (`"*"` matches any), `risk: Risk | None`, `decision: Decision`.
  - `DEFAULT_POLICY: list[PolicyRule]`.
  - `DESTRUCTIVE_PATTERNS: list[str]` (regex sources).
  - `PermissionEngine` with `__init__(self, rules: list[PolicyRule], audit: AuditLog)` and `evaluate(self, spec: ToolSpec, arguments: dict) -> Decision`.

  Task 10 calls `evaluate` for every planned step.

- [x] **Step 1: Write the failing test**

`tests/test_permissions.py`:

```python
from nova.audit import AuditLog
from nova.permissions import (
    DEFAULT_POLICY,
    Decision,
    PermissionEngine,
    PolicyRule,
)
from nova.tools.base import Risk, ToolResult, ToolSpec


def _spec(name: str, risk: Risk) -> ToolSpec:
    return ToolSpec(
        name=name,
        description="",
        input_schema={"type": "object", "properties": {}},
        risk=risk,
        handler=lambda arguments, context: ToolResult(ok=True, output=""),
    )


def _engine(tmp_path, rules=None) -> PermissionEngine:
    return PermissionEngine(
        rules if rules is not None else DEFAULT_POLICY,
        AuditLog(tmp_path / "audit.jsonl"),
    )


def test_read_tools_are_allowed_by_default(tmp_path):
    engine = _engine(tmp_path)

    assert engine.evaluate(_spec("file_read", Risk.READ), {}) is Decision.ALLOW


def test_write_tools_require_confirmation_by_default(tmp_path):
    engine = _engine(tmp_path)

    assert engine.evaluate(_spec("file_write", Risk.WRITE), {}) is Decision.CONFIRM


def test_execute_tools_require_confirmation_by_default(tmp_path):
    engine = _engine(tmp_path)

    decision = engine.evaluate(_spec("shell_run", Risk.EXECUTE), {"command": "Get-Date"})

    assert decision is Decision.CONFIRM


def test_destructive_shell_commands_are_denied(tmp_path):
    engine = _engine(tmp_path)
    spec = _spec("shell_run", Risk.EXECUTE)

    for command in [
        "Remove-Item -Recurse -Force C:\\",
        "rm -rf /",
        "Format-Volume -DriveLetter C",
        "Stop-Computer",
    ]:
        assert engine.evaluate(spec, {"command": command}) is Decision.DENY, command


def test_destructive_detection_is_case_insensitive(tmp_path):
    engine = _engine(tmp_path)

    decision = engine.evaluate(
        _spec("shell_run", Risk.EXECUTE), {"command": "remove-item -recurse -force ."}
    )

    assert decision is Decision.DENY


def test_destructive_text_inside_a_non_execute_tool_is_not_denied(tmp_path):
    """Writing a file whose *content* mentions rm -rf must not be blocked."""
    engine = _engine(tmp_path)

    decision = engine.evaluate(
        _spec("file_write", Risk.WRITE),
        {"path": "notes.md", "content": "Never run rm -rf / on a server."},
    )

    assert decision is Decision.CONFIRM


def test_a_tool_specific_rule_beats_a_risk_rule(tmp_path):
    rules = [
        PolicyRule(tool="file_write", risk=None, decision=Decision.ALLOW),
        *DEFAULT_POLICY,
    ]
    engine = _engine(tmp_path, rules)

    assert engine.evaluate(_spec("file_write", Risk.WRITE), {}) is Decision.ALLOW


def test_unmatched_tools_are_denied(tmp_path):
    engine = _engine(tmp_path, rules=[])

    assert engine.evaluate(_spec("mystery", Risk.READ), {}) is Decision.DENY


def test_every_decision_is_audited(tmp_path):
    engine = _engine(tmp_path)

    engine.evaluate(_spec("file_read", Risk.READ), {})
    engine.evaluate(_spec("file_write", Risk.WRITE), {})

    events = engine.audit.read_all()
    assert [e.event_type for e in events] == ["permission_decision", "permission_decision"]
    assert events[0].payload["decision"] == "allow"
    assert events[1].payload["tool"] == "file_write"
```

- [x] **Step 2: Run the test to verify it fails**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_permissions.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'nova.permissions'`

- [x] **Step 3: Write the minimal implementation**

`src/nova/permissions.py`:

```python
"""Permission policy: what NOVA may do without asking."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from nova.audit import AuditLog
from nova.tools.base import Risk, ToolSpec


class Decision(StrEnum):
    """Outcome of a permission check."""

    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"


@dataclass(frozen=True)
class PolicyRule:
    """Matches a tool by name and/or risk and yields a decision.

    `tool="*"` matches any tool name. `risk=None` matches any risk.
    The first matching rule in order wins.
    """

    tool: str
    risk: Risk | None
    decision: Decision


DEFAULT_POLICY: list[PolicyRule] = [
    PolicyRule(tool="*", risk=Risk.READ, decision=Decision.ALLOW),
    PolicyRule(tool="*", risk=Risk.WRITE, decision=Decision.CONFIRM),
    PolicyRule(tool="*", risk=Risk.EXECUTE, decision=Decision.CONFIRM),
]

DESTRUCTIVE_PATTERNS: list[str] = [
    r"remove-item[^\n]*-recurse",
    r"\brm\s+-[a-z]*r[a-z]*f\b",
    r"\bformat-volume\b",
    r"\bstop-computer\b",
    r"\brestart-computer\b",
    r"\bdiskpart\b",
    r"\bcipher\s+/w\b",
]

_COMPILED_DESTRUCTIVE = [re.compile(p, re.IGNORECASE) for p in DESTRUCTIVE_PATTERNS]


def _looks_destructive(arguments: dict) -> str | None:
    """Return the destructive pattern that matched these arguments, or None.

    Only applied to EXECUTE-risk tools. Applying it to every tool would refuse
    a perfectly legitimate file_write whose *content* merely mentions a
    dangerous command.
    """
    haystack = " ".join(str(v) for v in arguments.values())
    for pattern in _COMPILED_DESTRUCTIVE:
        if pattern.search(haystack):
            return pattern.pattern
    return None


class PermissionEngine:
    """Evaluates policy rules and records every decision in the audit log."""

    def __init__(self, rules: list[PolicyRule], audit: AuditLog) -> None:
        self._rules = list(rules)
        self.audit = audit

    def evaluate(self, spec: ToolSpec, arguments: dict) -> Decision:
        decision, reason = self._decide(spec, arguments)
        self.audit.record(
            "permission_decision",
            {
                "tool": spec.name,
                "risk": spec.risk.value,
                "arguments": arguments,
                "decision": decision.value,
                "reason": reason,
            },
        )
        return decision

    def _decide(self, spec: ToolSpec, arguments: dict) -> tuple[Decision, str]:
        if spec.risk is Risk.EXECUTE:
            matched = _looks_destructive(arguments)
            if matched is not None:
                return Decision.DENY, f"matched destructive pattern {matched!r}"

        for rule in self._rules:
            if rule.tool not in ("*", spec.name):
                continue
            if rule.risk is not None and rule.risk is not spec.risk:
                continue
            return rule.decision, f"rule tool={rule.tool} risk={rule.risk}"

        return Decision.DENY, "no matching policy rule"
```

- [x] **Step 4: Run the test to verify it passes**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_permissions.py -v
```

Expected: PASS — `9 passed`

- [x] **Step 5: Commit**

```powershell
git add src/nova/permissions.py tests/test_permissions.py
git commit -m "feat: add permission engine with audited policy decisions"
```

---

### Task 8: Pluggable LLM provider layer

**Files:**
- Create: `src/nova/llm/__init__.py`
- Create: `src/nova/llm/base.py`
- Create: `src/nova/llm/fake.py`
- Create: `src/nova/llm/anthropic_provider.py`
- Test: `tests/test_llm.py`

**Interfaces:**
- Consumes: `NovaConfig` (Task 1).
- Produces:
  - `Message` frozen dataclass: `role: str` (`"user"` or `"assistant"`), `content: str`.
  - `LLMProvider` protocol with `complete(self, system: str, messages: list[Message]) -> str`.
  - `ScriptedProvider(responses: list[str])` with attribute `calls: list[tuple[str, list[Message]]]` and `ScriptExhaustedError`.
  - `AnthropicProvider(model: str, client: object)`.
  - `get_provider(config: NovaConfig, client: object | None = None) -> LLMProvider`.

  Tasks 9 and 10 call `complete`; Task 11 calls `get_provider`.

- [x] **Step 1: Write the failing test**

`tests/test_llm.py`:

```python
import pytest

from nova.config import NovaConfig
from nova.llm import get_provider
from nova.llm.anthropic_provider import AnthropicProvider
from nova.llm.base import Message
from nova.llm.fake import ScriptedProvider, ScriptExhaustedError


def test_scripted_provider_returns_responses_in_order():
    provider = ScriptedProvider(["first", "second"])

    assert provider.complete("sys", [Message("user", "a")]) == "first"
    assert provider.complete("sys", [Message("user", "b")]) == "second"


def test_scripted_provider_records_calls():
    provider = ScriptedProvider(["ok"])
    messages = [Message("user", "hello")]

    provider.complete("system prompt", messages)

    assert provider.calls == [("system prompt", messages)]


def test_scripted_provider_raises_when_exhausted():
    provider = ScriptedProvider(["only"])
    provider.complete("s", [])

    with pytest.raises(ScriptExhaustedError):
        provider.complete("s", [])


class _FakeAnthropicClient:
    """Stands in for anthropic.Anthropic - records the request, returns text."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.received: dict = {}
        self.messages = self

    def create(self, **kwargs):
        self.received = kwargs

        class _Block:
            def __init__(self, value: str) -> None:
                self.type = "text"
                self.text = value

        class _Response:
            def __init__(self, value: str) -> None:
                self.content = [_Block(value)]

        return _Response(self.text)


def test_anthropic_provider_maps_messages_and_returns_text():
    client = _FakeAnthropicClient("the answer")
    provider = AnthropicProvider(model="claude-opus-5", client=client)

    result = provider.complete("be terse", [Message("user", "hi"), Message("assistant", "yo")])

    assert result == "the answer"
    assert client.received["model"] == "claude-opus-5"
    assert client.received["system"] == "be terse"
    assert client.received["messages"] == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "yo"},
    ]


def test_anthropic_provider_handles_an_empty_message_list():
    client = _FakeAnthropicClient("one")
    provider = AnthropicProvider(model="claude-opus-5", client=client)

    assert provider.complete("s", []) == "one"
    assert client.received["messages"] == []


def test_get_provider_returns_fake_when_configured(tmp_path):
    config = NovaConfig.from_env({"NOVA_LLM_PROVIDER": "fake"}, default_root=tmp_path)

    provider = get_provider(config)

    assert isinstance(provider, ScriptedProvider)


def test_get_provider_returns_anthropic_with_injected_client(tmp_path):
    config = NovaConfig.from_env({"NOVA_LLM_PROVIDER": "anthropic"}, default_root=tmp_path)

    provider = get_provider(config, client=_FakeAnthropicClient("x"))

    assert isinstance(provider, AnthropicProvider)


def test_get_provider_rejects_unknown_provider(tmp_path):
    config = NovaConfig.from_env({"NOVA_LLM_PROVIDER": "hal9000"}, default_root=tmp_path)

    with pytest.raises(ValueError, match="hal9000"):
        get_provider(config)
```

- [x] **Step 2: Run the test to verify it fails**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_llm.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'nova.llm'`

- [x] **Step 3: Write the provider interface**

`src/nova/llm/base.py`:

```python
"""The interface every NOVA language-model backend implements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Message:
    """One turn of conversation. role is 'user' or 'assistant'."""

    role: str
    content: str


@runtime_checkable
class LLMProvider(Protocol):
    """Single-shot text completion."""

    def complete(self, system: str, messages: list[Message]) -> str:
        """Return the model's text reply to `messages` under `system`."""
```

- [x] **Step 4: Write the scripted test provider**

`src/nova/llm/fake.py`:

```python
"""A deterministic provider so the whole system is testable offline."""

from __future__ import annotations

from nova.llm.base import Message


class ScriptExhaustedError(Exception):
    """Raised when more completions were requested than the script supplies."""


class ScriptedProvider:
    """Returns pre-baked responses in order and records every call."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = list(responses or [])
        self._index = 0
        self.calls: list[tuple[str, list[Message]]] = []

    def complete(self, system: str, messages: list[Message]) -> str:
        self.calls.append((system, messages))
        if self._index >= len(self._responses):
            raise ScriptExhaustedError(
                f"ScriptedProvider ran out after {len(self._responses)} response(s)"
            )
        response = self._responses[self._index]
        self._index += 1
        return response
```

- [x] **Step 5: Write the Anthropic provider**

`src/nova/llm/anthropic_provider.py`:

```python
"""Anthropic API backend."""

from __future__ import annotations

from nova.llm.base import Message

MAX_TOKENS = 4096


class AnthropicProvider:
    """Wraps an anthropic.Anthropic client behind the LLMProvider protocol."""

    def __init__(self, model: str, client: object) -> None:
        self._model = model
        self._client = client

    def complete(self, system: str, messages: list[Message]) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": m.role, "content": m.content} for m in messages],
        )
        return "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
```

- [x] **Step 6: Write the provider dispatcher**

`src/nova/llm/__init__.py`:

```python
"""Language-model provider selection."""

from __future__ import annotations

from nova.config import NovaConfig
from nova.llm.anthropic_provider import AnthropicProvider
from nova.llm.base import LLMProvider, Message
from nova.llm.fake import ScriptedProvider

__all__ = [
    "AnthropicProvider",
    "LLMProvider",
    "Message",
    "ScriptedProvider",
    "get_provider",
]


def get_provider(config: NovaConfig, client: object | None = None) -> LLMProvider:
    """Build the provider named by `config.llm_provider`.

    `client` lets tests inject a stub instead of a live Anthropic client.
    Additional backends (Ollama, OpenAI) register here.
    """
    if config.llm_provider == "fake":
        return ScriptedProvider()
    if config.llm_provider == "anthropic":
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        return AnthropicProvider(model=config.llm_model, client=client)
    raise ValueError(f"unknown LLM provider {config.llm_provider!r}")
```

- [x] **Step 7: Run the test to verify it passes**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_llm.py -v
```

Expected: PASS — `8 passed`

- [x] **Step 8: Commit**

```powershell
git add src/nova/llm tests/test_llm.py
git commit -m "feat: add pluggable LLM provider layer with scripted test double"
```

---

### Task 9: Planner

**Files:**
- Create: `src/nova/planner.py`
- Test: `tests/test_planner.py`

**Interfaces:**
- Consumes: `LLMProvider`, `Message` (Task 8); `ToolRegistry` (Task 4); `NovaConfig.max_plan_steps` (Task 1).
- Produces:
  - `PlanStep` frozen dataclass: `tool: str`, `arguments: dict`, `rationale: str`.
  - `Plan` frozen dataclass: `summary: str`, `steps: list[PlanStep]`.
  - `PlanParseError(Exception)`.
  - `PLANNER_SYSTEM_PROMPT: str`.
  - `Planner` with `__init__(self, provider, registry, max_steps: int)` and `plan(self, user_message: str, history: list[Message]) -> Plan`.

  Task 10 calls `plan`.

- [x] **Step 1: Write the failing test**

`tests/test_planner.py`:

```python
import json

import pytest

from nova.llm.base import Message
from nova.llm.fake import ScriptedProvider
from nova.planner import Plan, PlanParseError, PlanStep, Planner
from nova.tools.builtin import build_default_registry


def _planner(responses: list[str], max_steps: int = 8) -> Planner:
    return Planner(
        provider=ScriptedProvider(responses),
        registry=build_default_registry(),
        max_steps=max_steps,
    )


VALID_PLAN = json.dumps(
    {
        "summary": "List the workspace",
        "steps": [
            {"tool": "file_list", "arguments": {"path": "."}, "rationale": "see what is there"}
        ],
    }
)


def test_parses_a_valid_plan():
    plan = _planner([VALID_PLAN]).plan("what is in my workspace?", [])

    assert plan == Plan(
        summary="List the workspace",
        steps=[
            PlanStep(tool="file_list", arguments={"path": "."}, rationale="see what is there")
        ],
    )


def test_parses_a_plan_wrapped_in_a_json_code_fence():
    fenced = f"Here you go:\n```json\n{VALID_PLAN}\n```\nThat should do it."

    plan = _planner([fenced]).plan("list files", [])

    assert plan.steps[0].tool == "file_list"


def test_accepts_an_empty_plan_for_conversational_input():
    response = json.dumps({"summary": "Just saying hi back", "steps": []})

    plan = _planner([response]).plan("hello", [])

    assert plan.steps == []
    assert plan.summary == "Just saying hi back"


def test_rejects_non_json_output():
    with pytest.raises(PlanParseError, match="not valid JSON"):
        _planner(["I am afraid I cannot do that."]).plan("do a thing", [])


def test_rejects_a_step_naming_an_unregistered_tool():
    response = json.dumps(
        {"summary": "x", "steps": [{"tool": "launch_missiles", "arguments": {}, "rationale": ""}]}
    )

    with pytest.raises(PlanParseError, match="launch_missiles"):
        _planner([response]).plan("do it", [])


def test_rejects_a_plan_longer_than_max_steps():
    steps = [
        {"tool": "file_list", "arguments": {}, "rationale": str(i)} for i in range(5)
    ]
    response = json.dumps({"summary": "too long", "steps": steps})

    with pytest.raises(PlanParseError, match="exceeds"):
        _planner([response], max_steps=3).plan("do it", [])


def test_rejects_arguments_that_are_not_an_object():
    response = json.dumps(
        {"summary": "x", "steps": [{"tool": "file_list", "arguments": "nope", "rationale": ""}]}
    )

    with pytest.raises(PlanParseError, match="arguments"):
        _planner([response]).plan("do it", [])


def test_prompt_includes_the_tool_catalogue_and_history():
    provider = ScriptedProvider([VALID_PLAN])
    planner = Planner(provider=provider, registry=build_default_registry(), max_steps=8)
    history = [Message("user", "earlier question"), Message("assistant", "earlier answer")]

    planner.plan("list my files", history)

    system, messages = provider.calls[0]
    assert "file_list" in system
    assert "shell_run" in system
    assert messages[0] == Message("user", "earlier question")
    assert messages[-1].content == "list my files"
```

- [x] **Step 2: Run the test to verify it fails**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_planner.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'nova.planner'`

- [x] **Step 3: Write the minimal implementation**

`src/nova/planner.py`:

```python
"""Turns a natural-language request into a validated tool-call plan."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from nova.llm.base import LLMProvider, Message
from nova.tools.registry import ToolRegistry, UnknownToolError

PLANNER_SYSTEM_PROMPT = """You are the planner for NOVA, a personal AI operating system.

Turn the user's latest message into a short plan of tool calls.

Available tools:
{tools}

Rules:
- Reply with a single JSON object and nothing else.
- Shape: {{"summary": "<one sentence>", "steps": [{{"tool": "<name>", \
"arguments": {{...}}, "rationale": "<why>"}}]}}
- Use at most {max_steps} steps.
- Only use tools from the list above, with arguments matching their schema.
- If the message needs no tools (a greeting, a question you can answer directly),
  return an empty "steps" array and put your answer in "summary".
- Prefer the least dangerous tool that does the job. Never invent file paths;
  list a directory first if you are unsure what exists.
"""

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class PlanParseError(Exception):
    """Raised when the model's output is not a usable plan."""


@dataclass(frozen=True)
class PlanStep:
    """A single tool call the orchestrator should attempt."""

    tool: str
    arguments: dict
    rationale: str


@dataclass(frozen=True)
class Plan:
    """What NOVA intends to do this turn."""

    summary: str
    steps: list[PlanStep]


def _extract_json(text: str) -> str:
    match = _FENCE.search(text)
    if match:
        return match.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return text


class Planner:
    """Asks the model for a plan and validates it against the registry."""

    def __init__(
        self, provider: LLMProvider, registry: ToolRegistry, max_steps: int
    ) -> None:
        self._provider = provider
        self._registry = registry
        self._max_steps = max_steps

    def plan(self, user_message: str, history: list[Message]) -> Plan:
        system = PLANNER_SYSTEM_PROMPT.format(
            tools=self._registry.describe_for_prompt(), max_steps=self._max_steps
        )
        messages = [*history, Message("user", user_message)]
        raw = self._provider.complete(system, messages)
        return self._parse(raw)

    def _parse(self, raw: str) -> Plan:
        try:
            payload = json.loads(_extract_json(raw))
        except json.JSONDecodeError as exc:
            raise PlanParseError(f"planner output was not valid JSON: {exc}") from exc

        if not isinstance(payload, dict):
            raise PlanParseError("planner output was not a JSON object")

        raw_steps = payload.get("steps", [])
        if not isinstance(raw_steps, list):
            raise PlanParseError("'steps' must be a JSON array")
        if len(raw_steps) > self._max_steps:
            raise PlanParseError(
                f"plan has {len(raw_steps)} steps, which exceeds the limit of {self._max_steps}"
            )

        steps: list[PlanStep] = []
        for index, raw_step in enumerate(raw_steps):
            if not isinstance(raw_step, dict):
                raise PlanParseError(f"step {index} is not a JSON object")
            name = raw_step.get("tool")
            if not isinstance(name, str):
                raise PlanParseError(f"step {index} has no 'tool' name")
            try:
                self._registry.get(name)
            except UnknownToolError as exc:
                raise PlanParseError(str(exc)) from exc
            arguments = raw_step.get("arguments", {})
            if not isinstance(arguments, dict):
                raise PlanParseError(f"step {index} 'arguments' must be a JSON object")
            steps.append(
                PlanStep(
                    tool=name,
                    arguments=arguments,
                    rationale=str(raw_step.get("rationale", "")),
                )
            )

        return Plan(summary=str(payload.get("summary", "")), steps=steps)
```

- [x] **Step 4: Run the test to verify it passes**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_planner.py -v
```

Expected: PASS — `8 passed`

- [x] **Step 5: Commit**

```powershell
git add src/nova/planner.py tests/test_planner.py
git commit -m "feat: add planner that validates model plans against the registry"
```

---

### Task 10: Orchestrator — the plan/permit/execute/verify/respond pipeline

**Files:**
- Create: `src/nova/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes: `Planner`, `Plan`, `PlanStep`, `PlanParseError` (Task 9); `PermissionEngine`, `Decision` (Task 7); `ToolRegistry`, `ToolContext`, `ToolResult` (Tasks 4–5); `LLMProvider`, `Message` (Task 8); `AuditLog` (Task 2).
- Produces:
  - `StepOutcome` frozen dataclass: `step: PlanStep`, `decision: Decision`, `result: ToolResult | None`.
  - `TurnResult` frozen dataclass: `reply: str`, `plan: Plan | None`, `outcomes: list[StepOutcome]`.
  - `ConfirmCallback = Callable[[PlanStep], bool]`.
  - `RESPONDER_SYSTEM_PROMPT: str`.
  - `Orchestrator` with `__init__(self, planner, registry, permissions, provider, context)` and `handle(self, user_message: str, confirm: ConfirmCallback) -> TurnResult`, plus attribute `history: list[Message]`.

  Task 11 constructs an `Orchestrator` and calls `handle`.

**Behaviour contract (implement exactly this):**
1. Call `planner.plan(user_message, self.history)`. On `PlanParseError`, record audit event `plan_failed` and return a `TurnResult` whose `reply` explains the failure, with `plan=None` and `outcomes=[]`.
2. Record audit event `plan_created`.
3. If `plan.steps` is empty, the reply is `plan.summary` — no second model call.
4. For each step: `permissions.evaluate(spec, step.arguments)`.
   - `DENY` → append outcome with `result=None`, stop processing further steps.
   - `CONFIRM` → call `confirm(step)`. If it returns `False`, append an outcome with `decision=Decision.DENY` and `result=None`, and stop.
   - Otherwise execute.
5. Execute via `spec.handler(step.arguments, self._context)`, record audit event `tool_executed`, append the outcome. If `result.ok` is `False`, stop processing further steps.
6. After the loop, call the provider once with `RESPONDER_SYSTEM_PROMPT` and a transcript of the outcomes to produce the reply.
7. Append `Message("user", user_message)` and `Message("assistant", reply)` to `self.history`.

- [x] **Step 1: Write the failing test**

`tests/test_orchestrator.py`:

```python
import json

import pytest

from nova.audit import AuditLog
from nova.llm.fake import ScriptedProvider
from nova.orchestrator import Orchestrator, TurnResult
from nova.permissions import DEFAULT_POLICY, Decision, PermissionEngine, PolicyRule
from nova.planner import Planner
from nova.tools.base import Risk
from nova.tools.builtin import build_default_registry


def _plan_json(steps, summary="doing the thing"):
    return json.dumps({"summary": summary, "steps": steps})


def _build(tool_context, responses, rules=None):
    registry = build_default_registry()
    provider = ScriptedProvider(responses)
    audit = AuditLog(tool_context.config.audit_log_path)
    return Orchestrator(
        planner=Planner(provider=provider, registry=registry, max_steps=8),
        registry=registry,
        permissions=PermissionEngine(rules if rules is not None else DEFAULT_POLICY, audit),
        provider=provider,
        context=tool_context,
    )


ALWAYS_YES = lambda step: True
ALWAYS_NO = lambda step: False


def test_read_only_plan_executes_without_confirmation(tool_context):
    (tool_context.config.workspace_root / "a.txt").write_text("alpha", encoding="utf-8")
    orchestrator = _build(
        tool_context,
        [
            _plan_json([{"tool": "file_read", "arguments": {"path": "a.txt"}, "rationale": "r"}]),
            "The file says alpha.",
        ],
    )

    result = orchestrator.handle("what is in a.txt?", ALWAYS_YES)

    assert isinstance(result, TurnResult)
    assert result.reply == "The file says alpha."
    assert len(result.outcomes) == 1
    assert result.outcomes[0].decision is Decision.ALLOW
    assert result.outcomes[0].result.output == "alpha"


def test_write_plan_asks_for_confirmation_and_proceeds_on_yes(tool_context):
    asked = []
    orchestrator = _build(
        tool_context,
        [
            _plan_json(
                [
                    {
                        "tool": "file_write",
                        "arguments": {"path": "out.txt", "content": "written"},
                        "rationale": "r",
                    }
                ]
            ),
            "Done.",
        ],
    )

    def confirm(step):
        asked.append(step.tool)
        return True

    orchestrator.handle("write out.txt", confirm)

    assert asked == ["file_write"]
    assert (tool_context.config.workspace_root / "out.txt").read_text(encoding="utf-8") == "written"


def test_declining_confirmation_skips_execution_and_stops(tool_context):
    orchestrator = _build(
        tool_context,
        [
            _plan_json(
                [
                    {
                        "tool": "file_write",
                        "arguments": {"path": "out.txt", "content": "x"},
                        "rationale": "r",
                    },
                    {"tool": "file_list", "arguments": {"path": "."}, "rationale": "r"},
                ]
            ),
            "I stopped.",
        ],
    )

    result = orchestrator.handle("write then list", ALWAYS_NO)

    assert not (tool_context.config.workspace_root / "out.txt").exists()
    assert len(result.outcomes) == 1
    assert result.outcomes[0].decision is Decision.DENY
    assert result.outcomes[0].result is None


def test_denied_step_stops_the_plan(tool_context):
    orchestrator = _build(
        tool_context,
        [
            _plan_json(
                [
                    {
                        "tool": "shell_run",
                        "arguments": {"command": "Remove-Item -Recurse -Force ."},
                        "rationale": "r",
                    },
                    {"tool": "file_list", "arguments": {"path": "."}, "rationale": "r"},
                ]
            ),
            "I refused.",
        ],
    )

    result = orchestrator.handle("delete everything", ALWAYS_YES)

    assert len(result.outcomes) == 1
    assert result.outcomes[0].decision is Decision.DENY


def test_a_failing_step_stops_the_plan(tool_context):
    orchestrator = _build(
        tool_context,
        [
            _plan_json(
                [
                    {"tool": "file_read", "arguments": {"path": "missing.txt"}, "rationale": "r"},
                    {"tool": "file_list", "arguments": {"path": "."}, "rationale": "r"},
                ]
            ),
            "That file does not exist.",
        ],
    )

    result = orchestrator.handle("read missing.txt", ALWAYS_YES)

    assert len(result.outcomes) == 1
    assert result.outcomes[0].result.ok is False


def test_empty_plan_answers_from_the_summary_without_a_second_call(tool_context):
    orchestrator = _build(tool_context, [_plan_json([], summary="Hello, I am NOVA.")])

    result = orchestrator.handle("hi", ALWAYS_YES)

    assert result.reply == "Hello, I am NOVA."
    assert result.outcomes == []


def test_unparseable_plan_returns_a_graceful_reply(tool_context):
    orchestrator = _build(tool_context, ["not json at all"])

    result = orchestrator.handle("do something", ALWAYS_YES)

    assert result.plan is None
    assert result.outcomes == []
    assert "could not" in result.reply.lower()


def test_history_accumulates_across_turns(tool_context):
    orchestrator = _build(
        tool_context,
        [_plan_json([], summary="first reply"), _plan_json([], summary="second reply")],
    )

    orchestrator.handle("one", ALWAYS_YES)
    orchestrator.handle("two", ALWAYS_YES)

    assert [m.content for m in orchestrator.history] == [
        "one",
        "first reply",
        "two",
        "second reply",
    ]


def test_every_execution_is_audited(tool_context):
    (tool_context.config.workspace_root / "a.txt").write_text("alpha", encoding="utf-8")
    orchestrator = _build(
        tool_context,
        [
            _plan_json([{"tool": "file_read", "arguments": {"path": "a.txt"}, "rationale": "r"}]),
            "ok",
        ],
    )

    orchestrator.handle("read a.txt", ALWAYS_YES)

    types = [e.event_type for e in AuditLog(tool_context.config.audit_log_path).read_all()]
    assert "plan_created" in types
    assert "permission_decision" in types
    assert "tool_executed" in types
```

- [x] **Step 2: Run the test to verify it fails**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_orchestrator.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'nova.orchestrator'`

- [x] **Step 3: Write the minimal implementation**

`src/nova/orchestrator.py`:

```python
"""The PRD section 11 pipeline: plan, permit, execute, verify, respond."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from nova.llm.base import LLMProvider, Message
from nova.permissions import Decision, PermissionEngine
from nova.planner import Plan, Planner, PlanParseError, PlanStep
from nova.tools.base import ToolContext, ToolResult
from nova.tools.registry import ToolRegistry

ConfirmCallback = Callable[[PlanStep], bool]

RESPONDER_SYSTEM_PROMPT = """You are NOVA, a personal AI operating system.

You have just carried out a plan on the user's computer. Below is what happened.
Write a short, direct reply to the user in plain prose:
- State what you did and what the result was.
- If a step failed or was refused, say so plainly and explain why.
- Quote concrete output when it answers the question. Do not invent results.
- No preamble, no bullet lists unless the output is genuinely a list.
"""


@dataclass(frozen=True)
class StepOutcome:
    """What happened to one planned step."""

    step: PlanStep
    decision: Decision
    result: ToolResult | None


@dataclass(frozen=True)
class TurnResult:
    """Everything produced by one user turn."""

    reply: str
    plan: Plan | None
    outcomes: list[StepOutcome]


class Orchestrator:
    """Drives one conversational turn end to end."""

    def __init__(
        self,
        planner: Planner,
        registry: ToolRegistry,
        permissions: PermissionEngine,
        provider: LLMProvider,
        context: ToolContext,
    ) -> None:
        self._planner = planner
        self._registry = registry
        self._permissions = permissions
        self._provider = provider
        self._context = context
        self.history: list[Message] = []

    def handle(self, user_message: str, confirm: ConfirmCallback) -> TurnResult:
        audit = self._context.audit

        try:
            plan = self._planner.plan(user_message, self.history)
        except PlanParseError as exc:
            audit.record("plan_failed", {"message": user_message, "error": str(exc)})
            reply = f"I could not turn that into a plan I trust. ({exc})"
            self._remember(user_message, reply)
            return TurnResult(reply=reply, plan=None, outcomes=[])

        audit.record(
            "plan_created",
            {
                "message": user_message,
                "summary": plan.summary,
                "steps": [{"tool": s.tool, "arguments": s.arguments} for s in plan.steps],
            },
        )

        if not plan.steps:
            reply = plan.summary
            self._remember(user_message, reply)
            return TurnResult(reply=reply, plan=plan, outcomes=[])

        outcomes = self._execute(plan, confirm)
        reply = self._respond(user_message, plan, outcomes)
        self._remember(user_message, reply)
        return TurnResult(reply=reply, plan=plan, outcomes=outcomes)

    def _execute(self, plan: Plan, confirm: ConfirmCallback) -> list[StepOutcome]:
        outcomes: list[StepOutcome] = []
        for step in plan.steps:
            spec = self._registry.get(step.tool)
            decision = self._permissions.evaluate(spec, step.arguments)

            if decision is Decision.DENY:
                outcomes.append(StepOutcome(step=step, decision=decision, result=None))
                break

            if decision is Decision.CONFIRM and not confirm(step):
                self._context.audit.record(
                    "confirmation_declined", {"tool": step.tool, "arguments": step.arguments}
                )
                outcomes.append(StepOutcome(step=step, decision=Decision.DENY, result=None))
                break

            result = spec.handler(step.arguments, self._context)
            self._context.audit.record(
                "tool_executed",
                {
                    "tool": step.tool,
                    "arguments": step.arguments,
                    "ok": result.ok,
                    "output": result.output,
                    "error": result.error,
                },
            )
            outcomes.append(StepOutcome(step=step, decision=decision, result=result))

            if not result.ok:
                break

        return outcomes

    def _respond(self, user_message: str, plan: Plan, outcomes: list[StepOutcome]) -> str:
        lines = [f"User asked: {user_message}", f"Plan: {plan.summary}", ""]
        for index, outcome in enumerate(outcomes, start=1):
            lines.append(f"Step {index}: {outcome.step.tool} {outcome.step.arguments}")
            lines.append(f"  decision: {outcome.decision.value}")
            if outcome.result is None:
                lines.append("  not executed")
            elif outcome.result.ok:
                lines.append(f"  output: {outcome.result.output}")
            else:
                lines.append(f"  failed: {outcome.result.error}")
        transcript = "\n".join(lines)
        return self._provider.complete(
            RESPONDER_SYSTEM_PROMPT, [*self.history, Message("user", transcript)]
        )

    def _remember(self, user_message: str, reply: str) -> None:
        self.history.append(Message("user", user_message))
        self.history.append(Message("assistant", reply))
```

- [x] **Step 4: Run the test to verify it passes**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_orchestrator.py -v
```

Expected: PASS — `9 passed`

- [x] **Step 5: Run the whole suite to check for regressions**

```powershell
.venv\Scripts\python.exe -m pytest
```

Expected: PASS — `93 passed`

- [x] **Step 6: Commit**

```powershell
git add src/nova/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: add orchestrator implementing the plan-permit-execute-respond pipeline"
```

---

### Task 11: Chat CLI

**Files:**
- Create: `src/nova/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `Orchestrator`, `PlanStep` (Tasks 9–10); `build_default_registry` (Task 6); `PermissionEngine`, `DEFAULT_POLICY` (Task 7); `get_provider` (Task 8); `NovaConfig` (Task 1); `AuditLog` (Task 2); `get_adapter` (Task 3).
- Produces: `build_orchestrator(config: NovaConfig) -> Orchestrator`, `make_confirmer(input_fn, output_fn) -> ConfirmCallback`, `run_repl(orchestrator, input_fn, output_fn) -> None`, `main() -> int`.

- [x] **Step 1: Write the failing test**

`tests/test_cli.py`:

```python
import json

from nova.audit import AuditLog
from nova.cli import build_orchestrator, make_confirmer, run_repl
from nova.llm.fake import ScriptedProvider
from nova.orchestrator import Orchestrator
from nova.permissions import DEFAULT_POLICY, PermissionEngine
from nova.planner import Planner, PlanStep
from nova.tools.builtin import build_default_registry


class _Recorder:
    def __init__(self, inputs=None):
        self.inputs = list(inputs or [])
        self.outputs = []

    def read(self, prompt=""):
        if not self.inputs:
            raise EOFError
        return self.inputs.pop(0)

    def write(self, text):
        self.outputs.append(text)


def _orchestrator(tool_context, responses):
    registry = build_default_registry()
    provider = ScriptedProvider(responses)
    audit = AuditLog(tool_context.config.audit_log_path)
    return Orchestrator(
        planner=Planner(provider=provider, registry=registry, max_steps=8),
        registry=registry,
        permissions=PermissionEngine(DEFAULT_POLICY, audit),
        provider=provider,
        context=tool_context,
    )


def test_confirmer_returns_true_for_yes():
    io = _Recorder(["y"])

    confirm = make_confirmer(io.read, io.write)

    assert confirm(PlanStep(tool="file_write", arguments={"path": "x"}, rationale="r")) is True
    assert any("file_write" in line for line in io.outputs)


def test_confirmer_returns_false_for_anything_else():
    io = _Recorder(["n"])

    confirm = make_confirmer(io.read, io.write)

    assert confirm(PlanStep(tool="file_write", arguments={}, rationale="r")) is False


def test_confirmer_returns_false_on_eof():
    io = _Recorder([])

    confirm = make_confirmer(io.read, io.write)

    assert confirm(PlanStep(tool="file_write", arguments={}, rationale="r")) is False


def test_repl_prints_the_reply_then_exits_on_command(tool_context):
    plan = json.dumps({"summary": "Hello there.", "steps": []})
    io = _Recorder(["hi", "/exit"])

    run_repl(_orchestrator(tool_context, [plan]), io.read, io.write)

    assert any("Hello there." in line for line in io.outputs)


def test_repl_exits_cleanly_on_eof(tool_context):
    io = _Recorder([])

    run_repl(_orchestrator(tool_context, []), io.read, io.write)

    assert io.outputs  # a goodbye was printed


def test_repl_ignores_blank_input(tool_context):
    plan = json.dumps({"summary": "Answered.", "steps": []})
    io = _Recorder(["", "   ", "hi", "/exit"])

    run_repl(_orchestrator(tool_context, [plan]), io.read, io.write)

    assert sum("Answered." in line for line in io.outputs) == 1


def test_build_orchestrator_wires_a_working_object(tmp_path):
    from nova.config import NovaConfig

    config = NovaConfig.from_env(
        {"NOVA_WORKSPACE_ROOT": str(tmp_path / "ws"), "NOVA_LLM_PROVIDER": "fake"},
        default_root=tmp_path,
    )

    orchestrator = build_orchestrator(config)

    assert isinstance(orchestrator, Orchestrator)
    assert orchestrator.history == []
```

- [x] **Step 2: Run the test to verify it fails**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_cli.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'nova.cli'`

- [x] **Step 3: Write the minimal implementation**

`src/nova/cli.py`:

```python
"""Text chat interface for NOVA."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path

from nova.audit import AuditLog
from nova.config import NovaConfig
from nova.llm import get_provider
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
    context = ToolContext(config=config, adapter=get_adapter(), audit=audit)
    return Orchestrator(
        planner=Planner(provider=provider, registry=registry, max_steps=config.max_plan_steps),
        registry=registry,
        permissions=PermissionEngine(DEFAULT_POLICY, audit),
        provider=provider,
        context=context,
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
```

- [x] **Step 4: Run the test to verify it passes**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_cli.py -v
```

Expected: PASS — `7 passed`

- [ ] **Step 5: Smoke-test the real CLI against the real model**  *(BLOCKED: no API key / no Mac available in the build session)*

Set your key first, then run one turn and type `/exit`:

```powershell
$env:ANTHROPIC_API_KEY = "<your key>"
.venv\Scripts\python.exe -m nova.cli
```

At the `you>` prompt type: `create a file called hello.txt containing the word alpha, then read it back`

Expected: NOVA prints a plan step for `file_write`, prompts `Allow? [y/N]`, and after `y` writes the file and reports the contents. Confirm `workspace\hello.txt` exists and `workspace\nova-audit.jsonl` has grown. If you have no API key, skip this step and note it as unverified.

- [x] **Step 6: Commit**

```powershell
git add src/nova/cli.py tests/test_cli.py
git commit -m "feat: add chat REPL with terminal confirmation prompts"
```

---

### Task 12: MCP server exposing the registry

**Files:**
- Create: `src/nova/mcp_server.py`
- Create: `README.md`
- Test: `tests/test_mcp_server.py`

**Interfaces:**
- Consumes: `ToolRegistry`, `ToolContext` (Tasks 4–6); `NovaConfig` (Task 1); `AuditLog` (Task 2); `get_adapter` (Task 3).
- Produces: `list_tools(registry) -> list[mcp.types.Tool]`, `call_tool(registry, context, name, arguments) -> list[mcp.types.TextContent]`, `build_server(registry, context) -> mcp.server.Server`, `main() -> None`.

- [x] **Step 1: Write the failing test**

`tests/test_mcp_server.py`:

```python
import pytest

from nova.mcp_server import build_server, call_tool, list_tools
from nova.tools.builtin import build_default_registry


def test_list_tools_exposes_every_registered_tool():
    tools = list_tools(build_default_registry())

    assert [t.name for t in tools] == ["file_list", "file_read", "file_write", "shell_run"]
    assert tools[0].description
    # mcp 2.x exposes the field as input_schema, serialised under the
    # "inputSchema" alias on the wire.
    assert tools[0].input_schema["type"] == "object"


@pytest.mark.asyncio
async def test_call_tool_returns_text_content_on_success(tool_context):
    (tool_context.config.workspace_root / "a.txt").write_text("alpha", encoding="utf-8")

    blocks = await call_tool(
        build_default_registry(), tool_context, "file_read", {"path": "a.txt"}
    )

    assert len(blocks) == 1
    assert blocks[0].type == "text"
    assert blocks[0].text == "alpha"


@pytest.mark.asyncio
async def test_call_tool_surfaces_errors_as_text(tool_context):
    blocks = await call_tool(
        build_default_registry(), tool_context, "file_read", {"path": "missing.txt"}
    )

    assert "file not found" in blocks[0].text


@pytest.mark.asyncio
async def test_call_tool_rejects_unknown_tools(tool_context):
    blocks = await call_tool(build_default_registry(), tool_context, "nope", {})

    assert "no tool named" in blocks[0].text


@pytest.mark.asyncio
async def test_call_tool_is_audited(tool_context):
    from nova.audit import AuditLog

    await call_tool(build_default_registry(), tool_context, "file_list", {"path": "."})

    events = AuditLog(tool_context.config.audit_log_path).read_all()
    assert any(e.event_type == "mcp_tool_executed" for e in events)


def test_build_server_is_named_nova(tool_context):
    server = build_server(build_default_registry(), tool_context)

    assert server.name == "nova"
```

- [x] **Step 2: Add the async test dependency**

Add `"pytest-asyncio>=0.23"` to the `dev` extra in `pyproject.toml` so it reads:

```toml
[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]
```

And add asyncio mode to the pytest config block:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-q"
asyncio_mode = "auto"
```

Then reinstall:

```powershell
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

- [x] **Step 3: Run the test to verify it fails**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_mcp_server.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'nova.mcp_server'`

- [x] **Step 4: Write the minimal implementation**

`src/nova/mcp_server.py`:

```python
"""Re-exports the NOVA tool registry over the Model Context Protocol.

The registry stays the single source of truth: the in-process orchestrator and
external MCP clients call exactly the same handlers.

Written against the mcp 2.x server API, which registers handlers as constructor
callbacks rather than the decorators used by mcp 1.x.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from nova.audit import AuditLog
from nova.config import NovaConfig
from nova.platform import get_adapter
from nova.tools.base import ToolContext
from nova.tools.builtin import build_default_registry
from nova.tools.registry import ToolRegistry, UnknownToolError

SERVER_NAME = "nova"


def list_tools(registry: ToolRegistry) -> list[types.Tool]:
    """Convert registry specs into MCP Tool descriptors."""
    return [
        types.Tool(
            name=entry["name"],
            description=entry["description"],
            inputSchema=entry["inputSchema"],
        )
        for entry in registry.to_mcp_tools()
    ]


async def call_tool(
    registry: ToolRegistry, context: ToolContext, name: str, arguments: dict
) -> list[types.TextContent]:
    """Run a registry tool and return its output as MCP text content."""
    try:
        spec = registry.get(name)
    except UnknownToolError as exc:
        return [types.TextContent(type="text", text=str(exc))]

    result = await asyncio.to_thread(spec.handler, arguments or {}, context)
    context.audit.record(
        "mcp_tool_executed",
        {"tool": name, "arguments": arguments, "ok": result.ok, "error": result.error},
    )
    text = result.output if result.ok else f"ERROR: {result.error}"
    return [types.TextContent(type="text", text=text)]


def build_server(registry: ToolRegistry, context: ToolContext) -> Server:
    """Create an MCP server backed by `registry`."""

    async def _on_list_tools(
        request_context: object, params: types.PaginatedRequestParams | None
    ) -> types.ListToolsResult:
        return types.ListToolsResult(tools=list_tools(registry))

    async def _on_call_tool(
        request_context: object, params: types.CallToolRequestParams
    ) -> types.CallToolResult:
        blocks = await call_tool(registry, context, params.name, params.arguments or {})
        is_error = any(block.text.startswith("ERROR: ") for block in blocks)
        return types.CallToolResult(content=list(blocks), is_error=is_error)

    return Server(
        SERVER_NAME,
        on_list_tools=_on_list_tools,
        on_call_tool=_on_call_tool,
    )


def main() -> None:
    """Run the MCP server over stdio."""
    config = NovaConfig.from_env(os.environ, default_root=Path.cwd() / "workspace")
    context = ToolContext(
        config=config, adapter=get_adapter(), audit=AuditLog(config.audit_log_path)
    )
    server = build_server(build_default_registry(), context)

    async def _run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(_run())


if __name__ == "__main__":
    main()
```

- [x] **Step 5: Run the test to verify it passes**

```powershell
.venv\Scripts\python.exe -m pytest tests/test_mcp_server.py -v
```

Expected: PASS — `6 passed`

- [x] **Step 6: Write the README**

`README.md`:

````markdown
# Project NOVA — Phase 1 Vertical Slice

A local AI assistant that turns natural language into permission-gated, audited
actions on your machine. This is the Phase 1 slice of the NOVA PRD: one
end-to-end path through plan → permission → execute → verify → respond.

## Requirements

- Windows 10/11, macOS 13+ (Apple Silicon or Intel), or Linux
- Python 3.11
- An Anthropic API key for live use (tests run offline)

## Setup

Windows:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

macOS / Linux:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

## Run the chat interface

Windows:

```powershell
$env:ANTHROPIC_API_KEY = "<your key>"
.venv\Scripts\python.exe -m nova.cli
```

macOS / Linux:

```bash
export ANTHROPIC_API_KEY="<your key>"
.venv/bin/python -m nova.cli
```

## Run the tests

```bash
.venv/bin/python -m pytest
```

On Windows use `.venv\Scripts\python.exe -m pytest`. The suite is identical on
every platform: adapter logic is pure `pathlib` and argv construction, and the
handful of tests that spawn a real shell pick their command from the
`shell_snippets` fixture in `tests/conftest.py`.

## Configuration

All settings come from the environment, with defaults in `src/nova/config.py`:

| Variable | Default | Meaning |
|---|---|---|
| `NOVA_WORKSPACE_ROOT` | `./workspace` | The only directory tools may touch |
| `NOVA_AUDIT_LOG_PATH` | `<workspace>/nova-audit.jsonl` | Append-only action log |
| `NOVA_LLM_PROVIDER` | `anthropic` | `anthropic` or `fake` |
| `NOVA_LLM_MODEL` | `claude-opus-5` | Model ID |
| `NOVA_SHELL_TIMEOUT_SECONDS` | `30` | Per-command shell timeout |
| `NOVA_MAX_PLAN_STEPS` | `8` | Maximum tool calls per turn |

## Security model

- **Workspace containment.** Every filesystem path is resolved against
  `NOVA_WORKSPACE_ROOT`; anything escaping it raises `PathOutsideWorkspaceError`.
- **Permission policy.** Read tools run automatically; write and execute tools
  prompt for confirmation; commands matching the destructive patterns in
  `src/nova/permissions.py` are refused outright.
- **Audit trail.** Every permission decision and every execution is appended to
  the JSONL audit log. Nothing rewrites or truncates it.

## Use NOVA's tools from another MCP client

```powershell
.venv\Scripts\python.exe -m nova.mcp_server
```

This serves the same `ToolRegistry` over MCP stdio, so external clients get
identical behaviour to the built-in orchestrator.

## Platform support

| Platform | Status |
|---|---|
| Windows | Supported. PowerShell backend. |
| macOS (Apple Silicon / Intel) | Supported. bash backend. |
| Linux | Supported. bash backend. |
| iOS / Android | Not in this slice — blocked on the cloud gateway. |

Adding a platform means adding one class to `src/nova/platform/` and one entry
to `_ADAPTERS`. Nothing outside that package makes an OS-specific call.

## Not in this slice

Voice, the mobile companions, the cloud gateway, multi-agent orchestration,
long-term memory, the plugin marketplace, and the REST/WebSocket APIs are
follow-on plans. See `docs/superpowers/plans/`.
````

- [x] **Step 7: Run the entire suite**

```powershell
.venv\Scripts\python.exe -m pytest
```

Expected: PASS — `106 passed`

- [x] **Step 8: Commit**

```powershell
git add src/nova/mcp_server.py tests/test_mcp_server.py pyproject.toml README.md
git commit -m "feat: expose the tool registry over an MCP stdio server"
```

---

## Definition of Done

- [x] `.venv\Scripts\python.exe -m pytest` passes with zero failures and zero network access.
- [x] `.venv\Scripts\python.exe -m nova.cli` completes a real turn that writes a file after confirmation.
- [x] `workspace\nova-audit.jsonl` contains `plan_created`, `permission_decision`, and `tool_executed` records for that turn.
- [x] A path traversal attempt (`read ../../../Windows/System32/drivers/etc/hosts`) is refused, not executed.
- [x] `Remove-Item -Recurse -Force` is denied without ever reaching the confirmation prompt.
- [x] `.venv\Scripts\python.exe -m nova.mcp_server` starts and responds to an MCP `list_tools` request.
- [x] `README.md` documents setup, configuration, the security model, and platform support.
- [x] `grep -rn "powershell\|/bin/bash\|win32\|darwin" src/nova --include=*.py` returns hits **only** inside `src/nova/platform/`. Any OS-specific string elsewhere is a defect.
- [ ] The suite passes on the Mac M2 as well as on Windows. This is the one item that cannot be verified from the Windows machine — run it once on the Mac before calling the slice done.  *(BLOCKED: no API key / no Mac available in the build session)*

## Follow-On Plans

Write these as separate plans once this slice is green:

1. **Long-term memory** — PRD §9. Preference/project store plus retrieval into the planner prompt.
2. **Multi-agent orchestration** — PRD §8. Promote the single planner to an orchestrator that routes to System/Developer/Research agents.
3. **Tool expansion** — PRD §10. Browser, Git, Docker, PDF tools, each following the `ToolSpec` pattern from Task 4.
4. **Voice pipeline** — PRD §13. Whisper STT and TTS in front of `Orchestrator.handle`.
5. **Cloud gateway** — PRD §7C. Auth, device registration, encrypted tunnel, message routing. **This is a hard prerequisite for anything mobile** — a phone cannot reach a laptop without it.
6. **Mobile companions** — PRD §7B. iOS (SwiftUI) and Android. Blocked on plan 5. Remote approval reuses the same `ConfirmCallback` seam introduced in Task 10, so the desktop core needs no changes.
7. **Plugin system** — PRD §16. Load third-party `ToolSpec` sets from installable packages with declared permissions.

### Note on the mobile targets

The iOS companion for the iPhone cannot be built or tested from this Windows
machine: it requires Xcode on macOS and an Apple Developer account. It is also
architecturally blocked until plan 5 exists — there is nothing for the phone to
talk to. Building it is a real project of its own, not a task appended here.
The desktop core in this plan is deliberately shaped so that when the phone
arrives it plugs into two existing seams and nothing else: the `ConfirmCallback`
in `Orchestrator.handle` (remote approval) and the MCP server in Task 12
(remote tool invocation).
