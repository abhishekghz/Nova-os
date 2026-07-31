from nova.audit import AuditLog
from nova.permissions import (
    DEFAULT_POLICY,
    Decision,
    PermissionEngine,
    PolicyRule,
)
from nova.tools.base import Risk, ToolResult, ToolSpec


def _spec(name: str, risk: Risk) -> ToolSpec:
    return ToolSpec(
        name=name,
        description="",
        input_schema={"type": "object", "properties": {}},
        risk=risk,
        handler=lambda arguments, context: ToolResult(ok=True, output=""),
    )


def _engine(tmp_path, rules=None) -> PermissionEngine:
    return PermissionEngine(
        rules if rules is not None else DEFAULT_POLICY,
        AuditLog(tmp_path / "audit.jsonl"),
    )


def test_read_tools_are_allowed_by_default(tmp_path):
    engine = _engine(tmp_path)

    assert engine.evaluate(_spec("file_read", Risk.READ), {}) is Decision.ALLOW


def test_write_tools_require_confirmation_by_default(tmp_path):
    engine = _engine(tmp_path)

    assert engine.evaluate(_spec("file_write", Risk.WRITE), {}) is Decision.CONFIRM


def test_execute_tools_require_confirmation_by_default(tmp_path):
    engine = _engine(tmp_path)

    decision = engine.evaluate(_spec("shell_run", Risk.EXECUTE), {"command": "Get-Date"})

    assert decision is Decision.CONFIRM


def test_destructive_shell_commands_are_denied(tmp_path):
    engine = _engine(tmp_path)
    spec = _spec("shell_run", Risk.EXECUTE)

    for command in [
        "Remove-Item -Recurse -Force C:\\",
        "rm -rf /",
        "Format-Volume -DriveLetter C",
        "Stop-Computer",
    ]:
        assert engine.evaluate(spec, {"command": command}) is Decision.DENY, command


def test_destructive_detection_is_case_insensitive(tmp_path):
    engine = _engine(tmp_path)

    decision = engine.evaluate(
        _spec("shell_run", Risk.EXECUTE), {"command": "remove-item -recurse -force ."}
    )

    assert decision is Decision.DENY


def test_destructive_text_inside_a_non_execute_tool_is_not_denied(tmp_path):
    """Writing a file whose *content* mentions rm -rf must not be blocked."""
    engine = _engine(tmp_path)

    decision = engine.evaluate(
        _spec("file_write", Risk.WRITE),
        {"path": "notes.md", "content": "Never run rm -rf / on a server."},
    )

    assert decision is Decision.CONFIRM


def test_a_tool_specific_rule_beats_a_risk_rule(tmp_path):
    rules = [
        PolicyRule(tool="file_write", risk=None, decision=Decision.ALLOW),
        *DEFAULT_POLICY,
    ]
    engine = _engine(tmp_path, rules)

    assert engine.evaluate(_spec("file_write", Risk.WRITE), {}) is Decision.ALLOW


def test_unmatched_tools_are_denied(tmp_path):
    engine = _engine(tmp_path, rules=[])

    assert engine.evaluate(_spec("mystery", Risk.READ), {}) is Decision.DENY


def test_every_decision_is_audited(tmp_path):
    engine = _engine(tmp_path)

    engine.evaluate(_spec("file_read", Risk.READ), {})
    engine.evaluate(_spec("file_write", Risk.WRITE), {})

    events = engine.audit.read_all()
    assert [e.event_type for e in events] == ["permission_decision", "permission_decision"]
    assert events[0].payload["decision"] == "allow"
    assert events[1].payload["tool"] == "file_write"
