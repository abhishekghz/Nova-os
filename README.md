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
  prompt for confirmation; execute-risk commands matching the destructive
  patterns in `src/nova/permissions.py` are refused outright, before the
  confirmation prompt is ever reached.
- **Audit trail.** Every permission decision and every execution is appended to
  the JSONL audit log. Nothing rewrites or truncates it.

## Architecture

```
user message
     |
  Planner            LLM turns the message into a validated list of tool calls
     |
PermissionEngine     allow / confirm / deny, per tool risk and policy
     |
 ToolRegistry        the single source of truth for capabilities
     |
PlatformAdapter      Windows PowerShell | macOS bash | Linux bash
     |
  AuditLog           append-only JSONL record of everything above
```

`Orchestrator.handle()` in `src/nova/orchestrator.py` is the whole pipeline.

## Use NOVA's tools from another MCP client

```bash
.venv/bin/python -m nova.mcp_server
```

This serves the same `ToolRegistry` over MCP stdio, so external clients get
identical behaviour to the built-in orchestrator. Written against the mcp 2.x
server API.

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
