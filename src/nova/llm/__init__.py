"""Language-model provider selection."""

from __future__ import annotations

from nova.config import NovaConfig
from nova.llm.anthropic_provider import AnthropicProvider
from nova.llm.base import LLMProvider, Message
from nova.llm.fake import ScriptedProvider

__all__ = [
    "AnthropicProvider",
    "LLMProvider",
    "Message",
    "ScriptedProvider",
    "get_provider",
]


def get_provider(config: NovaConfig, client: object | None = None) -> LLMProvider:
    """Build the provider named by `config.llm_provider`.

    `client` lets tests inject a stub instead of a live Anthropic client.
    Additional backends (Ollama, OpenAI) register here.
    """
    if config.llm_provider == "fake":
        return ScriptedProvider()
    if config.llm_provider == "anthropic":
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        return AnthropicProvider(model=config.llm_model, client=client)
    raise ValueError(f"unknown LLM provider {config.llm_provider!r}")
