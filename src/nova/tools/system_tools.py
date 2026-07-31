"""Read-only machine inspection.

Uses only the standard library so it behaves the same on every platform and
adds no dependency.
"""

from __future__ import annotations

import os
import platform
import shutil
import sys

from nova.tools.base import Risk, ToolContext, ToolResult, ToolSpec


def _human_bytes(count: int) -> str:
    size = float(count)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"  # pragma: no cover - unreachable


def _system_info(arguments: dict, context: ToolContext) -> ToolResult:
    root = context.config.workspace_root
    usage = shutil.disk_usage(root)

    lines = [
        f"platform: {platform.system()} {platform.release()}",
        f"machine: {platform.machine()}",
        f"adapter: {context.adapter.name}",
        f"python: {sys.version.split()[0]}",
        f"cpu cores: {os.cpu_count()}",
        f"workspace: {root}",
        f"disk total: {_human_bytes(usage.total)}",
        f"disk free: {_human_bytes(usage.free)}",
    ]
    return ToolResult(ok=True, output="\n".join(lines))


SYSTEM_INFO = ToolSpec(
    name="system_info",
    description=(
        "Report the operating system, architecture, CPU count, Python version "
        "and workspace disk usage."
    ),
    input_schema={"type": "object", "properties": {}, "required": []},
    risk=Risk.READ,
    handler=_system_info,
)

SYSTEM_TOOLS = [SYSTEM_INFO]
