from nova.tools.base import Risk
from nova.tools.builtin import build_default_registry
from nova.tools.shell import SHELL_RUN


def test_shell_tool_metadata():
    assert SHELL_RUN.name == "shell_run"
    assert SHELL_RUN.risk is Risk.EXECUTE


def test_shell_run_captures_stdout(tool_context, shell_snippets):
    result = SHELL_RUN.handler({"command": shell_snippets["echo"]}, tool_context)

    assert result.ok is True
    assert "hello nova" in result.output


def test_shell_run_reports_nonzero_exit(tool_context, shell_snippets):
    result = SHELL_RUN.handler({"command": shell_snippets["fail"]}, tool_context)

    assert result.ok is False
    assert "exit code 3" in result.error


def test_shell_run_executes_in_the_workspace_root(tool_context, shell_snippets):
    result = SHELL_RUN.handler({"command": shell_snippets["cwd"]}, tool_context)

    assert result.ok is True
    # macOS reports /private/var/... where tmp_path says /var/..., so compare
    # the resolved leaf rather than the whole string.
    assert tool_context.config.workspace_root.name in result.output


def test_shell_run_times_out(tool_context, shell_snippets):
    from dataclasses import replace

    fast = replace(tool_context, config=replace(tool_context.config, shell_timeout_seconds=1))

    result = SHELL_RUN.handler({"command": shell_snippets["sleep"]}, fast)

    assert result.ok is False
    assert "timed out" in result.error


def test_shell_run_requires_a_command(tool_context):
    result = SHELL_RUN.handler({}, tool_context)

    assert result.ok is False
    assert "command" in result.error


def test_default_registry_contains_every_slice_tool():
    registry = build_default_registry()

    assert [s.name for s in registry.list_specs()] == [
        "file_list",
        "file_read",
        "file_write",
        "shell_run",
    ]
