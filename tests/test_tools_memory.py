from dataclasses import replace

from nova.tools.base import Risk
from nova.tools.memory_tools import (
    MEMORY_FORGET,
    MEMORY_RECALL,
    MEMORY_REMEMBER,
    MEMORY_TOOLS,
)


def test_tool_names_and_risks():
    assert MEMORY_REMEMBER.name == "memory_remember"
    assert MEMORY_REMEMBER.risk is Risk.WRITE
    assert MEMORY_RECALL.name == "memory_recall"
    assert MEMORY_RECALL.risk is Risk.READ
    assert MEMORY_FORGET.name == "memory_forget"
    assert MEMORY_FORGET.risk is Risk.WRITE
    assert MEMORY_TOOLS == [MEMORY_FORGET, MEMORY_RECALL, MEMORY_REMEMBER]


def test_remember_then_recall(tool_context):
    MEMORY_REMEMBER.handler(
        {"kind": "preference", "key": "editor", "value": "VS Code"}, tool_context
    )

    result = MEMORY_RECALL.handler({"query": "editor"}, tool_context)

    assert result.ok is True
    assert "VS Code" in result.output


def test_recall_with_no_match_is_still_ok(tool_context):
    result = MEMORY_RECALL.handler({"query": "nothing stored"}, tool_context)

    assert result.ok is True
    assert "nothing remembered" in result.output


def test_remember_rejects_an_unknown_kind(tool_context):
    result = MEMORY_REMEMBER.handler(
        {"kind": "wat", "key": "k", "value": "v"}, tool_context
    )

    assert result.ok is False
    assert "unknown memory kind" in result.error


def test_remember_requires_all_three_arguments(tool_context):
    result = MEMORY_REMEMBER.handler({"kind": "fact", "key": "k"}, tool_context)

    assert result.ok is False
    assert "value" in result.error


def test_forget_removes_a_memory(tool_context):
    MEMORY_REMEMBER.handler({"kind": "fact", "key": "k", "value": "v"}, tool_context)

    assert MEMORY_FORGET.handler({"key": "k"}, tool_context).ok is True
    assert "nothing remembered" in MEMORY_RECALL.handler({"query": "k"}, tool_context).output


def test_forget_on_a_missing_key_fails(tool_context):
    result = MEMORY_FORGET.handler({"key": "absent"}, tool_context)

    assert result.ok is False
    assert "nothing remembered" in result.error


def test_every_memory_tool_degrades_gracefully_without_a_store(tool_context):
    without = replace(tool_context, memory=None)

    for spec, args in (
        (MEMORY_REMEMBER, {"kind": "fact", "key": "k", "value": "v"}),
        (MEMORY_RECALL, {"query": "k"}),
        (MEMORY_FORGET, {"key": "k"}),
    ):
        result = spec.handler(args, without)
        assert result.ok is False, spec.name
        assert "not enabled" in result.error, spec.name


def test_memory_survives_within_a_session(tool_context):
    MEMORY_REMEMBER.handler(
        {"kind": "project", "key": "mri", "value": "MRI segmentation in PyTorch"},
        tool_context,
    )
    MEMORY_REMEMBER.handler(
        {"kind": "project", "key": "site", "value": "Portfolio site in Astro"},
        tool_context,
    )

    result = MEMORY_RECALL.handler({"query": "pytorch segmentation"}, tool_context)

    assert "MRI segmentation" in result.output
    assert "Portfolio" not in result.output
