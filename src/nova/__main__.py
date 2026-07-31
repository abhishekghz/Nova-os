"""Single entry point for the packaged application.

The bundled executable is one binary that can act as any of NOVA's three
front ends, chosen by the first argument:

    nova            interactive chat (default)
    nova serve      REST + WebSocket API
    nova mcp        MCP stdio server
    nova version    print the version and exit
"""

from __future__ import annotations

import sys

from nova import __version__

USAGE = """NOVA - personal AI operating system

Usage:
  nova                 Start the interactive chat interface (default)
  nova serve           Start the REST + WebSocket API server
  nova mcp             Start the MCP stdio server
  nova version         Print the version
  nova help            Show this message

Environment:
  ANTHROPIC_API_KEY            Required for live use
  NOVA_WORKSPACE_ROOT          Folder NOVA may touch (default ./workspace)
  NOVA_API_KEY                 API key for `nova serve` (generated if unset)
  NOVA_API_HOST, NOVA_API_PORT Where `nova serve` listens
"""


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    command = args[0].lower() if args else "chat"

    if command in {"help", "--help", "-h"}:
        print(USAGE)
        return 0

    if command in {"version", "--version", "-v"}:
        print(f"nova {__version__}")
        return 0

    if command in {"serve", "server"}:
        from nova.server import main as serve_main

        return serve_main()

    if command == "mcp":
        from nova.mcp_server import main as mcp_main

        mcp_main()
        return 0

    if command in {"chat", ""}:
        from nova.cli import main as chat_main

        return chat_main()

    print(f"Unknown command {command!r}.\n")
    print(USAGE)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
