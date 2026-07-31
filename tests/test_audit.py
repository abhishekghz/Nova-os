import json

from nova.audit import AuditEvent, AuditLog


def test_record_appends_one_json_line(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")

    event = log.record("tool_executed", {"tool": "file_read", "ok": True})

    lines = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    stored = json.loads(lines[0])
    assert stored["event_type"] == "tool_executed"
    assert stored["payload"] == {"tool": "file_read", "ok": True}
    assert stored["event_id"] == event.event_id


def test_record_creates_parent_directories(tmp_path):
    log = AuditLog(tmp_path / "nested" / "deeper" / "audit.jsonl")

    log.record("started", {})

    assert (tmp_path / "nested" / "deeper" / "audit.jsonl").is_file()


def test_read_all_returns_events_in_write_order(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")
    log.record("first", {"n": 1})
    log.record("second", {"n": 2})

    events = log.read_all()

    assert [e.event_type for e in events] == ["first", "second"]
    assert all(isinstance(e, AuditEvent) for e in events)


def test_event_ids_are_unique(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")

    ids = {log.record("tick", {}).event_id for _ in range(50)}

    assert len(ids) == 50


def test_timestamp_is_utc_iso8601(tmp_path):
    log = AuditLog(tmp_path / "audit.jsonl")

    event = log.record("tick", {})

    assert event.timestamp.endswith("+00:00")
