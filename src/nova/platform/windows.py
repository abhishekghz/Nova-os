"""Windows implementation of the platform adapter."""

from __future__ import annotations

from nova.platform.base import BaseAdapter


class WindowsAdapter(BaseAdapter):
    """PowerShell invocation for Windows hosts."""

    name = "windows"

    def shell_command(self, command: str) -> list[str]:
        return [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            command,
        ]
