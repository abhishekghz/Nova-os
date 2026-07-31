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
