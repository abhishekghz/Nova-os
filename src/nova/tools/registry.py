"""The single source of truth for what NOVA can do."""

from __future__ import annotations

import json

from nova.tools.base import ToolSpec


class UnknownToolError(Exception):
    """Raised when a plan references a tool that is not registered."""


class DuplicateToolError(Exception):
    """Raised when two tools claim the same name."""


class ToolRegistry:
    """Holds ToolSpecs and renders them for the LLM and for MCP clients."""

    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._specs:
            raise DuplicateToolError(f"tool {spec.name!r} is already registered")
        self._specs[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        try:
            return self._specs[name]
        except KeyError:
            raise UnknownToolError(f"no tool named {name!r}") from None

    def list_specs(self) -> list[ToolSpec]:
        return [self._specs[name] for name in sorted(self._specs)]

    def subset(self, names: tuple[str, ...] | list[str]) -> "ToolRegistry":
        """A registry holding only `names`. An empty selection means everything.

        Used to narrow what a specialist agent may reach for, so an agent
        cannot pick a tool outside its remit even if the model wants to.
        """
        if not names:
            return self
        scoped = ToolRegistry()
        for name in names:
            scoped.register(self.get(name))
        return scoped

    def to_mcp_tools(self) -> list[dict]:
        return [
            {
                "name": spec.name,
                "description": spec.description,
                "inputSchema": spec.input_schema,
            }
            for spec in self.list_specs()
        ]

    def describe_for_prompt(self) -> str:
        lines = []
        for spec in self.list_specs():
            lines.append(
                f"- {spec.name} (risk: {spec.risk.value}): {spec.description}\n"
                f"  arguments schema: {json.dumps(spec.input_schema)}"
            )
        return "\n".join(lines)
