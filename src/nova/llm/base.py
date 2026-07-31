"""The interface every NOVA language-model backend implements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Message:
    """One turn of conversation. role is 'user' or 'assistant'."""

    role: str
    content: str


@runtime_checkable
class LLMProvider(Protocol):
    """Single-shot text completion."""

    def complete(self, system: str, messages: list[Message]) -> str:
        """Return the model's text reply to `messages` under `system`."""
