"""macOS and Linux implementations of the platform adapter."""

from __future__ import annotations

from nova.platform.base import BaseAdapter

BASH = "/bin/bash"


class PosixAdapter(BaseAdapter):
    """Shared POSIX behaviour.

    bash is used rather than the user's login shell so that command semantics
    are identical on macOS (where the default is zsh) and Linux. `-c` rather
    than `-lc` keeps startup fast and avoids inheriting profile side effects.
    """

    def shell_command(self, command: str) -> list[str]:
        return [BASH, "-c", command]


class MacOSAdapter(PosixAdapter):
    """Apple Silicon and Intel macOS hosts."""

    name = "macos"


class LinuxAdapter(PosixAdapter):
    """Linux hosts."""

    name = "linux"
