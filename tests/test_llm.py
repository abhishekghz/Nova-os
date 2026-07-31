import pytest

from nova.config import NovaConfig
from nova.llm import get_provider
from nova.llm.anthropic_provider import AnthropicProvider
from nova.llm.base import Message
from nova.llm.fake import ScriptedProvider, ScriptExhaustedError


def test_scripted_provider_returns_responses_in_order():
    provider = ScriptedProvider(["first", "second"])

    assert provider.complete("sys", [Message("user", "a")]) == "first"
    assert provider.complete("sys", [Message("user", "b")]) == "second"


def test_scripted_provider_records_calls():
    provider = ScriptedProvider(["ok"])
    messages = [Message("user", "hello")]

    provider.complete("system prompt", messages)

    assert provider.calls == [("system prompt", messages)]


def test_scripted_provider_raises_when_exhausted():
    provider = ScriptedProvider(["only"])
    provider.complete("s", [])

    with pytest.raises(ScriptExhaustedError):
        provider.complete("s", [])


class _FakeAnthropicClient:
    """Stands in for anthropic.Anthropic - records the request, returns text."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.received: dict = {}
        self.messages = self

    def create(self, **kwargs):
        self.received = kwargs

        class _Block:
            def __init__(self, value: str) -> None:
                self.type = "text"
                self.text = value

        class _Response:
            def __init__(self, value: str) -> None:
                self.content = [_Block(value)]

        return _Response(self.text)


def test_anthropic_provider_maps_messages_and_returns_text():
    client = _FakeAnthropicClient("the answer")
    provider = AnthropicProvider(model="claude-opus-5", client=client)

    result = provider.complete("be terse", [Message("user", "hi"), Message("assistant", "yo")])

    assert result == "the answer"
    assert client.received["model"] == "claude-opus-5"
    assert client.received["system"] == "be terse"
    assert client.received["messages"] == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "yo"},
    ]


def test_anthropic_provider_handles_an_empty_message_list():
    client = _FakeAnthropicClient("one")
    provider = AnthropicProvider(model="claude-opus-5", client=client)

    assert provider.complete("s", []) == "one"
    assert client.received["messages"] == []


def test_get_provider_returns_fake_when_configured(tmp_path):
    config = NovaConfig.from_env({"NOVA_LLM_PROVIDER": "fake"}, default_root=tmp_path)

    provider = get_provider(config)

    assert isinstance(provider, ScriptedProvider)


def test_get_provider_returns_anthropic_with_injected_client(tmp_path):
    config = NovaConfig.from_env({"NOVA_LLM_PROVIDER": "anthropic"}, default_root=tmp_path)

    provider = get_provider(config, client=_FakeAnthropicClient("x"))

    assert isinstance(provider, AnthropicProvider)


def test_get_provider_rejects_unknown_provider(tmp_path):
    config = NovaConfig.from_env({"NOVA_LLM_PROVIDER": "hal9000"}, default_root=tmp_path)

    with pytest.raises(ValueError, match="hal9000"):
        get_provider(config)
