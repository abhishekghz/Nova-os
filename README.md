# NOVA

## 1. Install

Requires Python 3.11.

**Windows**

```powershell
git clone https://github.com/abhishekghz/Nova-os.git
cd Nova-os
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

**macOS / Linux**

```bash
git clone https://github.com/abhishekghz/Nova-os.git
cd Nova-os
python3.11 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

## 2. Set your API key

**Windows**

```powershell
$env:ANTHROPIC_API_KEY = "your-key-here"
```

**macOS / Linux**

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

## 3. Run

**Windows**

```powershell
.venv\Scripts\python.exe -m nova.cli
```

**macOS / Linux**

```bash
.venv/bin/python -m nova.cli
```

Type a request in plain language. Type `/exit` to quit.

```
you> list the files in my workspace
you> create notes.txt with my meeting agenda
you> what is in notes.txt
```

Actions that write files or run commands ask for confirmation first. Answer `y` to allow.

## 4. Settings

Set any of these before running.

| Variable | Default | Purpose |
|---|---|---|
| `NOVA_WORKSPACE_ROOT` | `./workspace` | The only folder NOVA may touch |
| `NOVA_AUDIT_LOG_PATH` | `<workspace>/nova-audit.jsonl` | Log of every action taken |
| `NOVA_SHELL_TIMEOUT_SECONDS` | `30` | Per-command timeout |
| `NOVA_MAX_PLAN_STEPS` | `8` | Max actions per request |

## 5. Run the tests

**Windows**

```powershell
.venv\Scripts\python.exe -m pytest
```

**macOS / Linux**

```bash
.venv/bin/python -m pytest
```

## 6. Use the tools from an MCP client

**Windows**

```powershell
.venv\Scripts\python.exe -m nova.mcp_server
```

**macOS / Linux**

```bash
.venv/bin/python -m nova.mcp_server
```
