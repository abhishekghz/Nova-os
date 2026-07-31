"""Append-only audit trail for every NOVA decision and execution."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class AuditEvent:
    """One immutable record of something NOVA decided or did."""

    event_id: str
    timestamp: str
    event_type: str
    payload: dict = field(default_factory=dict)


class AuditLog:
    """Writes AuditEvents as JSON Lines. Never rewrites or truncates."""

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def record(self, event_type: str, payload: dict) -> AuditEvent:
        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            event_type=event_type,
            payload=payload,
        )
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), default=str) + "\n")
        return event

    def read_all(self) -> list[AuditEvent]:
        if not self._path.is_file():
            return []
        events: list[AuditEvent] = []
        for line in self._path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            events.append(AuditEvent(**json.loads(line)))
        return events
