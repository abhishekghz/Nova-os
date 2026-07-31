"""Operating-system abstraction shared by all NOVA tools."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


class PathOutsideWorkspaceError(Exception):
    """Raised when a requested path escapes the configured workspace root."""


class UnsupportedPlatformError(Exception):
    """Raised when no adapter exists for the current operating system."""


def resolve_in_workspace(workspace_root: Path, relative: str) -> Path:
    """Resolve `relative` against `workspace_root`, refusing to escape it.

    Pure pathlib, so it behaves identically on every platform and can be
    exercised from any one of them.
    """
    root = Path(workspace_root).resolve()
    candidate = Path(root, relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise PathOutsideWorkspaceError(
            f"{candidate} is outside the workspace root {root}"
        )
    return candidate


@runtime_checkable
class PlatformAdapter(Protocol):
    """Everything NOVA needs to know about the host operating system."""

    name: str

    def resolve_in_workspace(self, workspace_root: Path, relative: str) -> Path:
        """Resolve `relative` against the workspace, refusing to escape it."""

    def shell_command(self, command: str) -> list[str]:
        """Return the argv that runs `command` in this platform's shell."""


class BaseAdapter:
    """Shared behaviour. Subclasses supply `name` and `shell_command`."""

    name: str = ""

    def resolve_in_workspace(self, workspace_root: Path, relative: str) -> Path:
        return resolve_in_workspace(workspace_root, relative)

    def shell_command(self, command: str) -> list[str]:
        raise NotImplementedError
