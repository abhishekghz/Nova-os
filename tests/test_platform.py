import pytest

from nova.platform import get_adapter
from nova.platform.base import (
    PathOutsideWorkspaceError,
    PlatformAdapter,
    UnsupportedPlatformError,
)
from nova.platform.posix import LinuxAdapter, MacOSAdapter
from nova.platform.windows import WindowsAdapter

ADAPTERS = [WindowsAdapter(), MacOSAdapter(), LinuxAdapter()]


@pytest.mark.parametrize(
    "adapter,expected",
    [(WindowsAdapter(), "windows"), (MacOSAdapter(), "macos"), (LinuxAdapter(), "linux")],
)
def test_adapter_reports_its_name(adapter, expected):
    assert adapter.name == expected


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_every_adapter_satisfies_the_protocol(adapter):
    assert isinstance(adapter, PlatformAdapter)


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_resolve_returns_path_inside_workspace(adapter, tmp_path):
    resolved = adapter.resolve_in_workspace(tmp_path, "notes/todo.txt")

    assert resolved == (tmp_path / "notes" / "todo.txt").resolve()


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_resolve_allows_the_root_itself(adapter, tmp_path):
    assert adapter.resolve_in_workspace(tmp_path, ".") == tmp_path.resolve()


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_resolve_rejects_parent_traversal(adapter, tmp_path):
    with pytest.raises(PathOutsideWorkspaceError):
        adapter.resolve_in_workspace(tmp_path, "../escaped.txt")


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_resolve_rejects_nested_parent_traversal(adapter, tmp_path):
    with pytest.raises(PathOutsideWorkspaceError):
        adapter.resolve_in_workspace(tmp_path, "a/b/../../../escaped.txt")


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_resolve_rejects_absolute_paths_outside_workspace(adapter, tmp_path):
    outside = str(tmp_path.parent / "escaped.txt")

    with pytest.raises(PathOutsideWorkspaceError):
        adapter.resolve_in_workspace(tmp_path, outside)


def test_windows_shell_command_builds_non_interactive_powershell_argv():
    assert WindowsAdapter().shell_command("Get-Date") == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        "Get-Date",
    ]


def test_macos_shell_command_builds_bash_argv():
    assert MacOSAdapter().shell_command("date") == ["/bin/bash", "-c", "date"]


def test_linux_shell_command_builds_bash_argv():
    assert LinuxAdapter().shell_command("date") == ["/bin/bash", "-c", "date"]


def test_get_adapter_returns_windows_adapter_for_win32():
    assert isinstance(get_adapter("win32"), WindowsAdapter)


def test_get_adapter_returns_macos_adapter_for_darwin():
    assert isinstance(get_adapter("darwin"), MacOSAdapter)


def test_get_adapter_returns_linux_adapter_for_linux():
    assert isinstance(get_adapter("linux"), LinuxAdapter)


def test_get_adapter_rejects_unknown_platforms():
    with pytest.raises(UnsupportedPlatformError):
        get_adapter("plan9")
