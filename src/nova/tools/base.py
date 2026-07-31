"""Core types every NOVA tool is built from."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from nova.audit import AuditLog
from nova.config import NovaConfig
from nova.platform.base import PlatformAdapter


class Risk(StrEnum):
    """How dangerous a tool is, which drives the permission policy."""

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"


@dataclass(frozen=True)
class ToolResult:
    """Outcome of a single tool invocation."""

    ok: bool
    output: str
    error: str | None = None


@dataclass(frozen=True)
class ToolContext:
    """Everything a tool handler is allowed to reach out to."""

    config: NovaConfig
    adapter: PlatformAdapter
    audit: AuditLog


@dataclass(frozen=True)
class ToolSpec:
    """A capability, described the way MCP describes tools."""

    name: str
    description: str
    input_schema: dict
    risk: Risk
    handler: Callable[[dict, ToolContext], ToolResult]
