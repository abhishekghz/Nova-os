import json

from nova.audit import AuditLog
from nova.llm.fake import ScriptedProvider
from nova.orchestrator import Orchestrator, TurnResult
from nova.permissions import DEFAULT_POLICY, Decision, PermissionEngine
from nova.planner import Planner
from nova.tools.builtin import build_default_registry


def _plan_json(steps, summary="doing the thing"):
    return json.dumps({"summary": summary, "steps": steps})


def _build(tool_context, responses, rules=None):
    registry = build_default_registry()
    provider = ScriptedProvider(responses)
    audit = AuditLog(tool_context.config.audit_log_path)
    return Orchestrator(
        planner=Planner(provider=provider, registry=registry, max_steps=8),
        registry=registry,
        permissions=PermissionEngine(rules if rules is not None else DEFAULT_POLICY, audit),
        provider=provider,
        context=tool_context,
    )


def ALWAYS_YES(step):
    return True


def ALWAYS_NO(step):
    return False


def test_read_only_plan_executes_without_confirmation(tool_context):
    (tool_context.config.workspace_root / "a.txt").write_text("alpha", encoding="utf-8")
    orchestrator = _build(
        tool_context,
        [
            _plan_json([{"tool": "file_read", "arguments": {"path": "a.txt"}, "rationale": "r"}]),
            "The file says alpha.",
        ],
    )

    result = orchestrator.handle("what is in a.txt?", ALWAYS_YES)

    assert isinstance(result, TurnResult)
    assert result.reply == "The file says alpha."
    assert len(result.outcomes) == 1
    assert result.outcomes[0].decision is Decision.ALLOW
    assert result.outcomes[0].result.output == "alpha"


def test_write_plan_asks_for_confirmation_and_proceeds_on_yes(tool_context):
    asked = []
    orchestrator = _build(
        tool_context,
        [
            _plan_json(
                [
                    {
                        "tool": "file_write",
                        "arguments": {"path": "out.txt", "content": "written"},
                        "rationale": "r",
                    }
                ]
            ),
            "Done.",
        ],
    )

    def confirm(step):
        asked.append(step.tool)
        return True

    orchestrator.handle("write out.txt", confirm)

    assert asked == ["file_write"]
    assert (tool_context.config.workspace_root / "out.txt").read_text(encoding="utf-8") == "written"


def test_declining_confirmation_skips_execution_and_stops(tool_context):
    orchestrator = _build(
        tool_context,
        [
            _plan_json(
                [
                    {
                        "tool": "file_write",
                        "arguments": {"path": "out.txt", "content": "x"},
                        "rationale": "r",
                    },
                    {"tool": "file_list", "arguments": {"path": "."}, "rationale": "r"},
                ]
            ),
            "I stopped.",
        ],
    )

    result = orchestrator.handle("write then list", ALWAYS_NO)

    assert not (tool_context.config.workspace_root / "out.txt").exists()
    assert len(result.outcomes) == 1
    assert result.outcomes[0].decision is Decision.DENY
    assert result.outcomes[0].result is None


def test_denied_step_stops_the_plan(tool_context):
    orchestrator = _build(
        tool_context,
        [
            _plan_json(
                [
                    {
                        "tool": "shell_run",
                        "arguments": {"command": "Remove-Item -Recurse -Force ."},
                        "rationale": "r",
                    },
                    {"tool": "file_list", "arguments": {"path": "."}, "rationale": "r"},
                ]
            ),
            "I refused.",
        ],
    )

    result = orchestrator.handle("delete everything", ALWAYS_YES)

    assert len(result.outcomes) == 1
    assert result.outcomes[0].decision is Decision.DENY


def test_a_failing_step_stops_the_plan(tool_context):
    orchestrator = _build(
        tool_context,
        [
            _plan_json(
                [
                    {"tool": "file_read", "arguments": {"path": "missing.txt"}, "rationale": "r"},
                    {"tool": "file_list", "arguments": {"path": "."}, "rationale": "r"},
                ]
            ),
            "That file does not exist.",
        ],
    )

    result = orchestrator.handle("read missing.txt", ALWAYS_YES)

    assert len(result.outcomes) == 1
    assert result.outcomes[0].result.ok is False


def test_empty_plan_answers_from_the_summary_without_a_second_call(tool_context):
    orchestrator = _build(tool_context, [_plan_json([], summary="Hello, I am NOVA.")])

    result = orchestrator.handle("hi", ALWAYS_YES)

    assert result.reply == "Hello, I am NOVA."
    assert result.outcomes == []


def test_unparseable_plan_returns_a_graceful_reply(tool_context):
    orchestrator = _build(tool_context, ["not json at all"])

    result = orchestrator.handle("do something", ALWAYS_YES)

    assert result.plan is None
    assert result.outcomes == []
    assert "could not" in result.reply.lower()


def test_history_accumulates_across_turns(tool_context):
    orchestrator = _build(
        tool_context,
        [_plan_json([], summary="first reply"), _plan_json([], summary="second reply")],
    )

    orchestrator.handle("one", ALWAYS_YES)
    orchestrator.handle("two", ALWAYS_YES)

    assert [m.content for m in orchestrator.history] == [
        "one",
        "first reply",
        "two",
        "second reply",
    ]


def test_every_execution_is_audited(tool_context):
    (tool_context.config.workspace_root / "a.txt").write_text("alpha", encoding="utf-8")
    orchestrator = _build(
        tool_context,
        [
            _plan_json([{"tool": "file_read", "arguments": {"path": "a.txt"}, "rationale": "r"}]),
            "ok",
        ],
    )

    orchestrator.handle("read a.txt", ALWAYS_YES)

    types = [e.event_type for e in AuditLog(tool_context.config.audit_log_path).read_all()]
    assert "plan_created" in types
    assert "permission_decision" in types
    assert "tool_executed" in types
