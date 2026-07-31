"""Platform adapter selection."""

from __future__ import annotations

import sys

from nova.platform.base import (
    BaseAdapter,
    PathOutsideWorkspaceError,
    PlatformAdapter,
    UnsupportedPlatformError,
    resolve_in_workspace,
)
from nova.platform.posix import LinuxAdapter, MacOSAdapter, PosixAdapter
from nova.platform.windows import WindowsAdapter

__all__ = [
    "BaseAdapter",
    "LinuxAdapter",
    "MacOSAdapter",
    "PathOutsideWorkspaceError",
    "PlatformAdapter",
    "PosixAdapter",
    "UnsupportedPlatformError",
    "WindowsAdapter",
    "get_adapter",
    "resolve_in_workspace",
]

_ADAPTERS = {
    "win32": WindowsAdapter,
    "darwin": MacOSAdapter,
    "linux": LinuxAdapter,
}


def get_adapter(platform_name: str | None = None) -> PlatformAdapter:
    """Return the adapter for `platform_name` (defaults to the running host)."""
    name = platform_name if platform_name is not None else sys.platform
    try:
        return _ADAPTERS[name]()
    except KeyError:
        raise UnsupportedPlatformError(
            f"no NOVA platform adapter for {name!r}; supported: {sorted(_ADAPTERS)}"
        ) from None
