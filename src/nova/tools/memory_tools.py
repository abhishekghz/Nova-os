"""Tools that let NOVA read and write its own long-term memory."""

from __future__ import annotations

from nova.memory.store import MEMORY_KINDS, UnknownMemoryKindError
from nova.tools.base import Risk, ToolContext, ToolResult, ToolSpec

NO_MEMORY = "long-term memory is not enabled in this session"


def _memory_remember(arguments: dict, context: ToolContext) -> ToolResult:
    if context.memory is None:
        return ToolResult(ok=False, output="", error=NO_MEMORY)

    kind = arguments.get("kind")
    key = arguments.get("key")
    value = arguments.get("value")
    for name, supplied in (("kind", kind), ("key", key), ("value", value)):
        if not isinstance(supplied, str) or not supplied:
            return ToolResult(
                ok=False,
                output="",
                error=f"argument {name!r} is required and must be a non-empty string",
            )

    try:
        record = context.memory.remember(kind, key, value)
    except UnknownMemoryKindError as exc:
        return ToolResult(ok=False, output="", error=str(exc))

    return ToolResult(ok=True, output=f"remembered [{record.kind}] {record.key}")


def _memory_recall(arguments: dict, context: ToolContext) -> ToolResult:
    if context.memory is None:
        return ToolResult(ok=False, output="", error=NO_MEMORY)

    query = arguments.get("query")
    if not isinstance(query, str) or not query:
        return ToolResult(
            ok=False,
            output="",
            error="argument 'query' is required and must be a non-empty string",
        )

    described = context.memory.describe_for_prompt(query)
    return ToolResult(ok=True, output=described or "(nothing remembered about that)")


def _memory_forget(arguments: dict, context: ToolContext) -> ToolResult:
    if context.memory is None:
        return ToolResult(ok=False, output="", error=NO_MEMORY)

    key = arguments.get("key")
    if not isinstance(key, str) or not key:
        return ToolResult(
            ok=False,
            output="",
            error="argument 'key' is required and must be a non-empty string",
        )

    if context.memory.forget(key):
        return ToolResult(ok=True, output=f"forgot {key}")
    return ToolResult(ok=False, output="", error=f"nothing remembered under {key!r}")


MEMORY_REMEMBER = ToolSpec(
    name="memory_remember",
    description=(
        "Save something durably so it is available in future sessions: a user "
        "preference, an ongoing project, a standing fact, or a saved workflow."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "kind": {
                "type": "string",
                "enum": list(MEMORY_KINDS),
                "description": "What sort of memory this is.",
            },
            "key": {
                "type": "string",
                "description": "Short stable identifier. Re-using a key overwrites it.",
            },
            "value": {"type": "string", "description": "The thing to remember."},
        },
        "required": ["kind", "key", "value"],
    },
    risk=Risk.WRITE,
    handler=_memory_remember,
)

MEMORY_RECALL = ToolSpec(
    name="memory_recall",
    description="Search long-term memory for anything relevant to a query.",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to look for."}
        },
        "required": ["query"],
    },
    risk=Risk.READ,
    handler=_memory_recall,
)

MEMORY_FORGET = ToolSpec(
    name="memory_forget",
    description="Permanently delete the memory stored under a key.",
    input_schema={
        "type": "object",
        "properties": {
            "key": {"type": "string", "description": "The key to delete."}
        },
        "required": ["key"],
    },
    risk=Risk.WRITE,
    handler=_memory_forget,
)

MEMORY_TOOLS = [MEMORY_FORGET, MEMORY_RECALL, MEMORY_REMEMBER]
