from nova.tools.base import Risk
from nova.tools.files import FILE_LIST, FILE_READ, FILE_TOOLS, FILE_WRITE


def test_tool_names_and_risks():
    assert FILE_READ.name == "file_read"
    assert FILE_READ.risk is Risk.READ
    assert FILE_WRITE.name == "file_write"
    assert FILE_WRITE.risk is Risk.WRITE
    assert FILE_LIST.name == "file_list"
    assert FILE_LIST.risk is Risk.READ
    assert FILE_TOOLS == [FILE_LIST, FILE_READ, FILE_WRITE]


def test_file_write_then_file_read_round_trips(tool_context):
    write_result = FILE_WRITE.handler(
        {"path": "notes/hello.txt", "content": "hello nova"}, tool_context
    )
    assert write_result.ok is True

    read_result = FILE_READ.handler({"path": "notes/hello.txt"}, tool_context)

    assert read_result.ok is True
    assert read_result.output == "hello nova"


def test_file_write_creates_parent_directories(tool_context):
    FILE_WRITE.handler({"path": "a/b/c/deep.txt", "content": "x"}, tool_context)

    assert (tool_context.config.workspace_root / "a" / "b" / "c" / "deep.txt").is_file()


def test_file_read_missing_file_fails_without_raising(tool_context):
    result = FILE_READ.handler({"path": "absent.txt"}, tool_context)

    assert result.ok is False
    assert "not found" in result.error


def test_file_read_refuses_paths_outside_the_workspace(tool_context):
    result = FILE_READ.handler({"path": "../../secrets.txt"}, tool_context)

    assert result.ok is False
    assert "outside the workspace" in result.error


def test_file_write_refuses_paths_outside_the_workspace(tool_context):
    result = FILE_WRITE.handler({"path": "../evil.txt", "content": "x"}, tool_context)

    assert result.ok is False
    assert "outside the workspace" in result.error
    assert not (tool_context.config.workspace_root.parent / "evil.txt").exists()


def test_file_list_reports_files_and_directories(tool_context):
    FILE_WRITE.handler({"path": "one.txt", "content": "1"}, tool_context)
    FILE_WRITE.handler({"path": "sub/two.txt", "content": "2"}, tool_context)

    result = FILE_LIST.handler({"path": "."}, tool_context)

    assert result.ok is True
    assert "one.txt" in result.output
    assert "sub/" in result.output


def test_file_list_on_missing_directory_fails(tool_context):
    result = FILE_LIST.handler({"path": "nowhere"}, tool_context)

    assert result.ok is False
    assert "not a directory" in result.error


def test_missing_required_argument_fails(tool_context):
    result = FILE_READ.handler({}, tool_context)

    assert result.ok is False
    assert "path" in result.error
