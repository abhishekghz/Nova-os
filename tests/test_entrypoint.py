import nova
from nova.__main__ import USAGE, main


def test_version_command_prints_the_version(capsys):
    assert main(["version"]) == 0
    assert nova.__version__ in capsys.readouterr().out


def test_version_flag_works(capsys):
    assert main(["--version"]) == 0
    assert nova.__version__ in capsys.readouterr().out


def test_help_command_prints_usage(capsys):
    assert main(["help"]) == 0
    assert "Usage:" in capsys.readouterr().out


def test_help_flag_works(capsys):
    assert main(["-h"]) == 0
    assert "Usage:" in capsys.readouterr().out


def test_unknown_command_exits_nonzero_and_explains(capsys):
    assert main(["frobnicate"]) == 2
    out = capsys.readouterr().out
    assert "Unknown command" in out
    assert "Usage:" in out


def test_usage_documents_every_command():
    for command in ("serve", "mcp", "version", "help"):
        assert command in USAGE


def test_usage_documents_the_required_environment():
    assert "ANTHROPIC_API_KEY" in USAGE
    assert "NOVA_WORKSPACE_ROOT" in USAGE


def test_serve_dispatches_to_the_server(monkeypatch):
    called = []
    import nova.server

    monkeypatch.setattr(nova.server, "main", lambda: called.append("serve") or 0)

    assert main(["serve"]) == 0
    assert called == ["serve"]


def test_mcp_dispatches_to_the_mcp_server(monkeypatch):
    called = []
    import nova.mcp_server

    monkeypatch.setattr(nova.mcp_server, "main", lambda: called.append("mcp"))

    assert main(["mcp"]) == 0
    assert called == ["mcp"]


def test_no_arguments_dispatches_to_chat(monkeypatch):
    called = []
    import nova.cli

    monkeypatch.setattr(nova.cli, "main", lambda: called.append("chat") or 0)

    assert main([]) == 0
    assert called == ["chat"]
