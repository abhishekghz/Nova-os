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
