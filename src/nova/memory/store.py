"""SQLite-backed long-term memory.

Retrieval is deliberately keyword-based rather than embedding-based: it needs no
model, no network and no extra dependency, and it is fully deterministic, which
means it can be tested exactly. A vector backend can replace `recall()` later
without changing any caller.
"""

from __future__ import annotations

import re
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

MEMORY_KINDS = ("preference", "project", "fact", "workflow")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    kind       TEXT NOT NULL,
    key        TEXT NOT NULL UNIQUE,
    value      TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_memories_kind ON memories(kind);
"""

_TOKEN = re.compile(r"[a-z0-9]+")

# Words too common to carry any signal when scoring overlap.
_STOPWORDS = frozenset(
    """a an and are as at be by for from has have i in is it its of on or that
    the to was were will with my me you your""".split()
)


class UnknownMemoryKindError(Exception):
    """Raised when a memory is stored under a kind NOVA does not recognise."""


@dataclass(frozen=True)
class MemoryRecord:
    """One remembered thing."""

    id: int
    kind: str
    key: str
    value: str
    created_at: str
    updated_at: str


def _tokenize(text: str) -> set[str]:
    return {t for t in _TOKEN.findall(text.lower()) if t not in _STOPWORDS}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryStore:
    """Durable key/value memory with keyword retrieval.

    Safe to share across threads: the API serves requests on a threadpool, so
    the connection is opened with `check_same_thread=False` and every statement
    runs under a lock. SQLite itself serialises writes; the lock is what makes
    the Python-side connection object safe to share.
    """

    def __init__(self, db_path: Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    @property
    def path(self) -> Path:
        return self._path

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def remember(self, kind: str, key: str, value: str) -> MemoryRecord:
        """Insert or update the memory stored under `key`."""
        if kind not in MEMORY_KINDS:
            raise UnknownMemoryKindError(
                f"unknown memory kind {kind!r}; expected one of {MEMORY_KINDS}"
            )
        now = _now()
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO memories (kind, key, value, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    kind = excluded.kind,
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (kind, key, value, now, now),
            )
            self._conn.commit()
        record = self.get(key)
        assert record is not None  # just written
        return record

    def get(self, key: str) -> MemoryRecord | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM memories WHERE key = ?", (key,)
            ).fetchone()
        return _to_record(row) if row is not None else None

    def forget(self, key: str) -> bool:
        with self._lock:
            cursor = self._conn.execute("DELETE FROM memories WHERE key = ?", (key,))
            self._conn.commit()
            return cursor.rowcount > 0

    def all(self) -> list[MemoryRecord]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM memories ORDER BY key").fetchall()
        return [_to_record(r) for r in rows]

    def recall(self, query: str, limit: int = 5) -> list[MemoryRecord]:
        """Return the memories whose text overlaps `query` most, best first."""
        wanted = _tokenize(query)
        if not wanted:
            return []

        scored: list[tuple[int, str, MemoryRecord]] = []
        for record in self.all():
            haystack = _tokenize(f"{record.key} {record.value}")
            score = len(wanted & haystack)
            if score:
                scored.append((score, record.key, record))

        scored.sort(key=lambda item: (-item[0], item[1]))
        return [record for _, _, record in scored[:limit]]

    def describe_for_prompt(self, query: str, limit: int = 5) -> str:
        """Render the memories relevant to `query` for injection into a prompt."""
        matches = self.recall(query, limit=limit)
        if not matches:
            return ""
        return "\n".join(f"- [{r.kind}] {r.key}: {r.value}" for r in matches)


def _to_record(row: sqlite3.Row) -> MemoryRecord:
    return MemoryRecord(
        id=row["id"],
        kind=row["kind"],
        key=row["key"],
        value=row["value"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
