"""Third-party capability loading.

A plugin is any installed distribution that advertises a `nova.plugins` entry
point resolving to a callable which returns `ToolSpec` objects:

    [project.entry-points."nova.plugins"]
    my_plugin = "my_package:tools"

    def tools() -> list[ToolSpec]:
        return [MY_TOOL]

Plugins extend the registry without touching the core: the orchestrator, the
permission engine and the MCP server all pick them up automatically, and the
same risk-based permission policy applies to them as to built-in tools.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import EntryPoint, entry_points

from nova.audit import AuditLog
from nova.tools.base import ToolSpec
from nova.tools.registry import DuplicateToolError, ToolRegistry

ENTRY_POINT_GROUP = "nova.plugins"


@dataclass(frozen=True)
class PluginLoadResult:
    """What happened when plugins were loaded."""

    loaded: dict[str, list[str]]  # plugin name -> tool names it contributed
    failed: dict[str, str]  # plugin name -> why it failed

    @property
    def tool_count(self) -> int:
        return sum(len(names) for names in self.loaded.values())


def _discover(group: str) -> list[EntryPoint]:
    found = entry_points()
    try:
        return list(found.select(group=group))
    except AttributeError:  # pragma: no cover - very old importlib.metadata
        return list(found.get(group, []))


def load_plugins(
    registry: ToolRegistry,
    audit: AuditLog | None = None,
    group: str = ENTRY_POINT_GROUP,
    discovered: list[EntryPoint] | None = None,
) -> PluginLoadResult:
    """Register every tool advertised by installed plugins.

    A plugin that raises, returns the wrong type, or collides with an existing
    tool name is skipped and recorded — one bad plugin must never stop NOVA
    from starting.
    """
    loaded: dict[str, list[str]] = {}
    failed: dict[str, str] = {}

    for entry in discovered if discovered is not None else _discover(group):
        try:
            factory = entry.load()
            specs = factory()
            if not isinstance(specs, (list, tuple)):
                raise TypeError(
                    f"expected a list of ToolSpec, got {type(specs).__name__}"
                )
            names: list[str] = []
            for spec in specs:
                if not isinstance(spec, ToolSpec):
                    raise TypeError(
                        f"expected ToolSpec objects, got {type(spec).__name__}"
                    )
                registry.register(spec)
                names.append(spec.name)
            loaded[entry.name] = names
        except DuplicateToolError as exc:
            failed[entry.name] = f"tool name collision: {exc}"
        except Exception as exc:  # noqa: BLE001 - a plugin must not crash startup
            failed[entry.name] = f"{type(exc).__name__}: {exc}"

    if audit is not None:
        audit.record("plugins_loaded", {"loaded": loaded, "failed": failed})

    return PluginLoadResult(loaded=loaded, failed=failed)
