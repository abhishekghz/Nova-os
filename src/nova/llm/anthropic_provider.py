"""Anthropic API backend."""

from __future__ import annotations

from nova.llm.base import Message

MAX_TOKENS = 4096


class AnthropicProvider:
    """Wraps an anthropic.Anthropic client behind the LLMProvider protocol."""

    def __init__(self, model: str, client: object) -> None:
        self._model = model
        self._client = client

    def complete(self, system: str, messages: list[Message]) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": m.role, "content": m.content} for m in messages],
        )
        return "".join(
            block.text for block in response.content if getattr(block, "type", "") == "text"
        )
