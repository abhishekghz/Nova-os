import json

import pytest

from nova.llm.base import Message
from nova.llm.fake import ScriptedProvider
from nova.planner import Plan, PlanParseError, PlanStep, Planner
from nova.tools.builtin import build_default_registry


def _planner(responses: list[str], max_steps: int = 8) -> Planner:
    return Planner(
        provider=ScriptedProvider(responses),
        registry=build_default_registry(),
        max_steps=max_steps,
    )


VALID_PLAN = json.dumps(
    {
        "summary": "List the workspace",
        "steps": [
            {"tool": "file_list", "arguments": {"path": "."}, "rationale": "see what is there"}
        ],
    }
)


def test_parses_a_valid_plan():
    plan = _planner([VALID_PLAN]).plan("what is in my workspace?", [])

    assert plan == Plan(
        summary="List the workspace",
        steps=[
            PlanStep(tool="file_list", arguments={"path": "."}, rationale="see what is there")
        ],
    )


def test_parses_a_plan_wrapped_in_a_json_code_fence():
    fenced = f"Here you go:\n```json\n{VALID_PLAN}\n```\nThat should do it."

    plan = _planner([fenced]).plan("list files", [])

    assert plan.steps[0].tool == "file_list"


def test_accepts_an_empty_plan_for_conversational_input():
    response = json.dumps({"summary": "Just saying hi back", "steps": []})

    plan = _planner([response]).plan("hello", [])

    assert plan.steps == []
    assert plan.summary == "Just saying hi back"


def test_rejects_non_json_output():
    with pytest.raises(PlanParseError, match="not valid JSON"):
        _planner(["I am afraid I cannot do that."]).plan("do a thing", [])


def test_rejects_a_step_naming_an_unregistered_tool():
    response = json.dumps(
        {"summary": "x", "steps": [{"tool": "launch_missiles", "arguments": {}, "rationale": ""}]}
    )

    with pytest.raises(PlanParseError, match="launch_missiles"):
        _planner([response]).plan("do it", [])


def test_rejects_a_plan_longer_than_max_steps():
    steps = [
        {"tool": "file_list", "arguments": {}, "rationale": str(i)} for i in range(5)
    ]
    response = json.dumps({"summary": "too long", "steps": steps})

    with pytest.raises(PlanParseError, match="exceeds"):
        _planner([response], max_steps=3).plan("do it", [])


def test_rejects_arguments_that_are_not_an_object():
    response = json.dumps(
        {"summary": "x", "steps": [{"tool": "file_list", "arguments": "nope", "rationale": ""}]}
    )

    with pytest.raises(PlanParseError, match="arguments"):
        _planner([response]).plan("do it", [])


def test_prompt_says_nothing_remembered_without_a_memory_store():
    provider = ScriptedProvider([VALID_PLAN])
    planner = Planner(provider=provider, registry=build_default_registry(), max_steps=8)

    planner.plan("anything", [])

    system, _ = provider.calls[0]
    assert "(nothing relevant remembered)" in system


def test_prompt_injects_relevant_long_term_memory(tmp_path):
    from nova.memory.store import MemoryStore

    store = MemoryStore(tmp_path / "m.db")
    try:
        store.remember("preference", "editor", "VS Code")
        store.remember("project", "mri", "MRI segmentation in PyTorch")
        provider = ScriptedProvider([VALID_PLAN])
        planner = Planner(
            provider=provider,
            registry=build_default_registry(),
            max_steps=8,
            memory=store,
        )

        planner.plan("open my editor", [])

        system, _ = provider.calls[0]
        assert "VS Code" in system
        assert "MRI segmentation" not in system  # irrelevant memory is not injected
    finally:
        store.close()


def test_prompt_includes_the_tool_catalogue_and_history():
    provider = ScriptedProvider([VALID_PLAN])
    planner = Planner(provider=provider, registry=build_default_registry(), max_steps=8)
    history = [Message("user", "earlier question"), Message("assistant", "earlier answer")]

    planner.plan("list my files", history)

    system, messages = provider.calls[0]
    assert "file_list" in system
    assert "shell_run" in system
    assert messages[0] == Message("user", "earlier question")
    assert messages[-1].content == "list my files"
