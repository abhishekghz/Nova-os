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
