# NOVA

## 1. Download

Grab the build for your machine from the
[latest release](https://github.com/abhishekghz/Nova-os/releases/latest).
No Python needed.

| Platform | File |
|---|---|
| Windows | `nova-windows-x64.exe` |
| macOS (Apple Silicon) | `nova-macos-arm64` |
| Linux | `nova-linux-x64` |

On macOS and Linux, make it executable first:

```bash
chmod +x nova-macos-arm64
```

Then skip to step 3.

## 2. Or install from source

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

## 3. Set your API key

**Windows**

```powershell
$env:ANTHROPIC_API_KEY = "your-key-here"
```

**macOS / Linux**

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

## 4. Run

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

If you downloaded the binary, run it directly instead:

```bash
./nova-windows-x64.exe
```

## 5. Run the API server

```bash
./nova-windows-x64.exe serve
```

It prints an API key on start. Send it as the `X-API-Key` header.

```bash
curl -H "X-API-Key: YOUR-KEY" http://127.0.0.1:8765/tools
```

```bash
curl -X POST http://127.0.0.1:8765/chat -H "X-API-Key: YOUR-KEY" -H "Content-Type: application/json" -d "{\"message\": \"list my files\"}"
```

From source, use `.venv\Scripts\python.exe -m nova.server` on Windows or
`.venv/bin/python -m nova.server` on macOS and Linux.

## 6. Settings

Set any of these before running.

| Variable | Default | Purpose |
|---|---|---|
| `NOVA_WORKSPACE_ROOT` | `./workspace` | The only folder NOVA may touch |
| `NOVA_AUDIT_LOG_PATH` | `<workspace>/nova-audit.jsonl` | Log of every action taken |
| `NOVA_SHELL_TIMEOUT_SECONDS` | `30` | Per-command timeout |
| `NOVA_MAX_PLAN_STEPS` | `8` | Max actions per request |
| `NOVA_API_KEY` | generated | Key for the API server |
| `NOVA_API_HOST` | `127.0.0.1` | API server bind address |
| `NOVA_API_PORT` | `8765` | API server port |

## 7. Run the tests

**Windows**

```powershell
.venv\Scripts\python.exe -m pytest
```

**macOS / Linux**

```bash
.venv/bin/python -m pytest
```

## 8. Use the tools from an MCP client

**Windows**

```powershell
.venv\Scripts\python.exe -m nova.mcp_server
```

**macOS / Linux**

```bash
.venv/bin/python -m nova.mcp_server
```
