from nova.audit import AuditLog
from nova.plugins import ENTRY_POINT_GROUP, PluginLoadResult, load_plugins
from nova.tools.base import Risk, ToolResult, ToolSpec
from nova.tools.builtin import build_default_registry
from nova.tools.registry import ToolRegistry


def _spec(name: str) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=f"{name} from a plugin",
        input_schema={"type": "object", "properties": {}, "required": []},
        risk=Risk.READ,
        handler=lambda arguments, context: ToolResult(ok=True, output=name),
    )


class _FakeEntryPoint:
    """Stands in for importlib.metadata.EntryPoint."""

    def __init__(self, name, factory):
        self.name = name
        self._factory = factory

    def load(self):
        return self._factory


def test_group_name_is_stable():
    assert ENTRY_POINT_GROUP == "nova.plugins"


def test_loads_tools_from_a_plugin():
    registry = ToolRegistry()

    result = load_plugins(
        registry, discovered=[_FakeEntryPoint("demo", lambda: [_spec("demo_tool")])]
    )

    assert result.loaded == {"demo": ["demo_tool"]}
    assert result.failed == {}
    assert registry.get("demo_tool").description == "demo_tool from a plugin"


def test_loads_several_tools_from_one_plugin():
    registry = ToolRegistry()

    result = load_plugins(
        registry,
        discovered=[_FakeEntryPoint("multi", lambda: [_spec("a"), _spec("b")])],
    )

    assert result.loaded == {"multi": ["a", "b"]}
    assert result.tool_count == 2


def test_plugin_tools_reach_the_default_registry():
    registry = build_default_registry()
    before = len(registry.list_specs())

    load_plugins(registry, discovered=[_FakeEntryPoint("x", lambda: [_spec("extra")])])

    assert len(registry.list_specs()) == before + 1
    assert registry.get("extra")


def test_a_raising_plugin_is_recorded_not_fatal():
    registry = ToolRegistry()

    def explode():
        raise RuntimeError("boom")

    result = load_plugins(registry, discovered=[_FakeEntryPoint("bad", explode)])

    assert result.loaded == {}
    assert "boom" in result.failed["bad"]


def test_a_plugin_returning_the_wrong_type_is_recorded():
    registry = ToolRegistry()

    result = load_plugins(registry, discovered=[_FakeEntryPoint("bad", lambda: "nope")])

    assert "expected a list of ToolSpec" in result.failed["bad"]


def test_a_plugin_yielding_non_toolspecs_is_recorded():
    registry = ToolRegistry()

    result = load_plugins(registry, discovered=[_FakeEntryPoint("bad", lambda: [42])])

    assert "expected ToolSpec objects" in result.failed["bad"]


def test_a_name_collision_is_recorded_not_fatal():
    registry = build_default_registry()

    result = load_plugins(
        registry, discovered=[_FakeEntryPoint("clash", lambda: [_spec("file_read")])]
    )

    assert result.loaded == {}
    assert "collision" in result.failed["clash"]


def test_one_bad_plugin_does_not_stop_a_good_one():
    registry = ToolRegistry()

    def explode():
        raise RuntimeError("boom")

    result = load_plugins(
        registry,
        discovered=[
            _FakeEntryPoint("bad", explode),
            _FakeEntryPoint("good", lambda: [_spec("works")]),
        ],
    )

    assert result.loaded == {"good": ["works"]}
    assert "bad" in result.failed
    assert registry.get("works")


def test_loading_is_audited(tmp_path):
    audit = AuditLog(tmp_path / "audit.jsonl")

    load_plugins(
        ToolRegistry(),
        audit=audit,
        discovered=[_FakeEntryPoint("demo", lambda: [_spec("t")])],
    )

    events = [e for e in audit.read_all() if e.event_type == "plugins_loaded"]
    assert events[0].payload["loaded"] == {"demo": ["t"]}


def test_no_plugins_installed_is_a_clean_no_op():
    result = load_plugins(ToolRegistry(), discovered=[])

    assert result == PluginLoadResult(loaded={}, failed={})
    assert result.tool_count == 0


def test_real_discovery_does_not_raise():
    """The live entry-point scan must work even with nothing installed."""
    result = load_plugins(ToolRegistry())

    assert isinstance(result, PluginLoadResult)
