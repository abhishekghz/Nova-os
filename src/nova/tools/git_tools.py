"""Read-only git inspection tools.

git is invoked directly rather than through the platform shell: the argv is
identical on every OS and there is no quoting to get wrong.
"""

from __future__ import annotations

import subprocess

from nova.tools.base import Risk, ToolContext, ToolResult, ToolSpec

MAX_OUTPUT_CHARS = 20_000
NOT_A_REPO = "the workspace is not a git repository"


def _truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + "\n... [truncated]"


def _run_git(args: list[str], context: ToolContext) -> ToolResult:
    try:
        completed = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            timeout=context.config.shell_timeout_seconds,
            cwd=context.config.workspace_root,
            check=False,
        )
    except FileNotFoundError:
        return ToolResult(ok=False, output="", error="git is not installed")
    except subprocess.TimeoutExpired:
        return ToolResult(
            ok=False,
            output="",
            error=f"git timed out after {context.config.shell_timeout_seconds}s",
        )

    stdout = _truncate(completed.stdout.strip())
    stderr = _truncate(completed.stderr.strip())

    if completed.returncode != 0:
        detail = stderr or stdout or "(no output)"
        if "not a git repository" in detail.lower():
            return ToolResult(ok=False, output="", error=NOT_A_REPO)
        return ToolResult(ok=False, output=stdout, error=detail)

    return ToolResult(ok=True, output=stdout or "(no output)")


def _git_status(arguments: dict, context: ToolContext) -> ToolResult:
    return _run_git(["status", "--porcelain=v1", "--branch"], context)


def _git_log(arguments: dict, context: ToolContext) -> ToolResult:
    limit = arguments.get("limit", 10)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
        return ToolResult(
            ok=False, output="", error="argument 'limit' must be an integer from 1 to 100"
        )
    return _run_git(["log", "--oneline", "--no-decorate", f"-n{limit}"], context)


def _git_diff(arguments: dict, context: ToolContext) -> ToolResult:
    staged = arguments.get("staged", False)
    if not isinstance(staged, bool):
        return ToolResult(ok=False, output="", error="argument 'staged' must be true or false")
    args = ["diff", "--stat"]
    if staged:
        args.insert(1, "--staged")
    return _run_git(args, context)


GIT_STATUS = ToolSpec(
    name="git_status",
    description="Show the git working-tree status of the workspace, if it is a repository.",
    input_schema={"type": "object", "properties": {}, "required": []},
    risk=Risk.READ,
    handler=_git_status,
)

GIT_LOG = ToolSpec(
    name="git_log",
    description="Show recent git commits in the workspace, most recent first.",
    input_schema={
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "description": "How many commits to show. Defaults to 10.",
            }
        },
        "required": [],
    },
    risk=Risk.READ,
    handler=_git_log,
)

GIT_DIFF = ToolSpec(
    name="git_diff",
    description="Show a summary of uncommitted changes in the workspace.",
    input_schema={
        "type": "object",
        "properties": {
            "staged": {
                "type": "boolean",
                "description": "Show staged changes instead of unstaged. Defaults to false.",
            }
        },
        "required": [],
    },
    risk=Risk.READ,
    handler=_git_diff,
)

GIT_TOOLS = [GIT_DIFF, GIT_LOG, GIT_STATUS]
