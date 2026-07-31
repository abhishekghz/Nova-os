"""A deterministic provider so the whole system is testable offline."""

from __future__ import annotations

from nova.llm.base import Message


class ScriptExhaustedError(Exception):
    """Raised when more completions were requested than the script supplies."""


class ScriptedProvider:
    """Returns pre-baked responses in order and records every call."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = list(responses or [])
        self._index = 0
        self.calls: list[tuple[str, list[Message]]] = []

    def complete(self, system: str, messages: list[Message]) -> str:
        self.calls.append((system, messages))
        if self._index >= len(self._responses):
            raise ScriptExhaustedError(
                f"ScriptedProvider ran out after {len(self._responses)} response(s)"
            )
        response = self._responses[self._index]
        self._index += 1
        return response
