"""Assembles the tool registry NOVA ships with."""

from __future__ import annotations

from nova.tools.files import FILE_TOOLS
from nova.tools.registry import ToolRegistry
from nova.tools.shell import SHELL_RUN


def build_default_registry() -> ToolRegistry:
    """Return a registry populated with every built-in tool."""
    registry = ToolRegistry()
    for spec in [*FILE_TOOLS, SHELL_RUN]:
        registry.register(spec)
    return registry
