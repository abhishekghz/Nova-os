"""Per-conversation orchestrator instances.

Each session owns its own Orchestrator, so two clients talking to the same
NOVA process do not bleed conversation history into one another.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from nova.orchestrator import Orchestrator


class SessionManager:
    """Thread-safe map of session id to Orchestrator."""

    def __init__(self, factory: Callable[[], Orchestrator]) -> None:
        self._factory = factory
        self._sessions: dict[str, Orchestrator] = {}
        self._lock = threading.Lock()

    def get(self, session_id: str) -> Orchestrator:
        """Return the session's orchestrator, creating it on first use."""
        with self._lock:
            if session_id not in self._sessions:
                self._sessions[session_id] = self._factory()
            return self._sessions[session_id]

    def drop(self, session_id: str) -> bool:
        """Forget a session. Returns whether it existed."""
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def ids(self) -> list[str]:
        with self._lock:
            return sorted(self._sessions)

    def __len__(self) -> int:
        with self._lock:
            return len(self._sessions)
