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
