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
        "Run a single shell command with the workspace root as the working "
        "directory and return its output. Use for system inspection and automation. "
        "The host shell is PowerShell on Windows and bash on macOS and Linux."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "The shell command to run."}
        },
        "required": ["command"],
    },
    risk=Risk.EXECUTE,
    handler=_shell_run,
)
