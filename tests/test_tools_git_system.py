import subprocess

import pytest

from nova.tools.base import Risk
from nova.tools.git_tools import GIT_DIFF, GIT_LOG, GIT_STATUS, GIT_TOOLS
from nova.tools.system_tools import SYSTEM_INFO


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def git_workspace(tool_context):
    """A workspace that is a real git repository with one commit."""
    root = tool_context.config.workspace_root
    _git(["init", "-q"], root)
    _git(["config", "user.email", "test@example.com"], root)
    _git(["config", "user.name", "Test"], root)
    (root / "tracked.txt").write_text("first\n", encoding="utf-8")
    _git(["add", "tracked.txt"], root)
    _git(["commit", "-q", "-m", "initial commit"], root)
    return tool_context


# --- metadata ------------------------------------------------------------


def test_git_tool_metadata():
    assert GIT_STATUS.name == "git_status"
    assert GIT_LOG.name == "git_log"
    assert GIT_DIFF.name == "git_diff"
    assert all(spec.risk is Risk.READ for spec in GIT_TOOLS)


def test_system_tool_metadata():
    assert SYSTEM_INFO.name == "system_info"
    assert SYSTEM_INFO.risk is Risk.READ


# --- git on a real repository -------------------------------------------


def test_git_status_reports_a_clean_tree(git_workspace):
    result = GIT_STATUS.handler({}, git_workspace)

    assert result.ok is True
    assert "##" in result.output  # the --branch header line


def test_git_status_reports_an_untracked_file(git_workspace):
    (git_workspace.config.workspace_root / "new.txt").write_text("x", encoding="utf-8")

    result = GIT_STATUS.handler({}, git_workspace)

    assert "new.txt" in result.output


def test_git_log_shows_the_commit(git_workspace):
    result = GIT_LOG.handler({}, git_workspace)

    assert result.ok is True
    assert "initial commit" in result.output


def test_git_log_honours_the_limit(git_workspace):
    root = git_workspace.config.workspace_root
    for i in range(3):
        (root / f"f{i}.txt").write_text("x", encoding="utf-8")
        _git(["add", "-A"], root)
        _git(["commit", "-q", "-m", f"commit {i}"], root)

    result = GIT_LOG.handler({"limit": 2}, git_workspace)

    assert len(result.output.splitlines()) == 2


def test_git_log_rejects_a_bad_limit(git_workspace):
    for bad in (0, 101, "ten", True):
        result = GIT_LOG.handler({"limit": bad}, git_workspace)
        assert result.ok is False, bad
        assert "limit" in result.error


def test_git_diff_reports_an_edit(git_workspace):
    root = git_workspace.config.workspace_root
    (root / "tracked.txt").write_text("first\nsecond\n", encoding="utf-8")

    result = GIT_DIFF.handler({}, git_workspace)

    assert result.ok is True
    assert "tracked.txt" in result.output


def test_git_diff_staged_reports_staged_changes(git_workspace):
    root = git_workspace.config.workspace_root
    (root / "tracked.txt").write_text("first\nsecond\n", encoding="utf-8")
    _git(["add", "tracked.txt"], root)

    result = GIT_DIFF.handler({"staged": True}, git_workspace)

    assert "tracked.txt" in result.output


def test_git_diff_rejects_a_non_boolean_staged(git_workspace):
    result = GIT_DIFF.handler({"staged": "yes"}, git_workspace)

    assert result.ok is False
    assert "staged" in result.error


# --- git outside a repository -------------------------------------------


def test_git_status_outside_a_repository_fails_cleanly(tool_context):
    result = GIT_STATUS.handler({}, tool_context)

    assert result.ok is False
    assert "not a git repository" in result.error


# --- system info ---------------------------------------------------------


def test_system_info_reports_the_essentials(tool_context):
    result = SYSTEM_INFO.handler({}, tool_context)

    assert result.ok is True
    for field in ("platform:", "machine:", "adapter:", "python:", "cpu cores:", "disk free:"):
        assert field in result.output, field


def test_system_info_names_the_active_adapter(tool_context):
    result = SYSTEM_INFO.handler({}, tool_context)

    assert tool_context.adapter.name in result.output


def test_system_info_points_at_the_workspace(tool_context):
    result = SYSTEM_INFO.handler({}, tool_context)

    assert str(tool_context.config.workspace_root) in result.output
