import json

from nova.audit import AuditLog
from nova.cli import build_orchestrator, make_confirmer, run_repl
from nova.llm.fake import ScriptedProvider
from nova.orchestrator import Orchestrator
from nova.permissions import DEFAULT_POLICY, PermissionEngine
from nova.planner import Planner, PlanStep
from nova.tools.builtin import build_default_registry


class _Recorder:
    def __init__(self, inputs=None):
        self.inputs = list(inputs or [])
        self.outputs = []

    def read(self, prompt=""):
        if not self.inputs:
            raise EOFError
        return self.inputs.pop(0)

    def write(self, text):
        self.outputs.append(text)


def _orchestrator(tool_context, responses):
    registry = build_default_registry()
    provider = ScriptedProvider(responses)
    audit = AuditLog(tool_context.config.audit_log_path)
    return Orchestrator(
        planner=Planner(provider=provider, registry=registry, max_steps=8),
        registry=registry,
        permissions=PermissionEngine(DEFAULT_POLICY, audit),
        provider=provider,
        context=tool_context,
    )


def test_confirmer_returns_true_for_yes():
    io = _Recorder(["y"])

    confirm = make_confirmer(io.read, io.write)

    assert confirm(PlanStep(tool="file_write", arguments={"path": "x"}, rationale="r")) is True
    assert any("file_write" in line for line in io.outputs)


def test_confirmer_returns_false_for_anything_else():
    io = _Recorder(["n"])

    confirm = make_confirmer(io.read, io.write)

    assert confirm(PlanStep(tool="file_write", arguments={}, rationale="r")) is False


def test_confirmer_returns_false_on_eof():
    io = _Recorder([])

    confirm = make_confirmer(io.read, io.write)

    assert confirm(PlanStep(tool="file_write", arguments={}, rationale="r")) is False


def test_repl_prints_the_reply_then_exits_on_command(tool_context):
    plan = json.dumps({"summary": "Hello there.", "steps": []})
    io = _Recorder(["hi", "/exit"])

    run_repl(_orchestrator(tool_context, [plan]), io.read, io.write)

    assert any("Hello there." in line for line in io.outputs)


def test_repl_exits_cleanly_on_eof(tool_context):
    io = _Recorder([])

    run_repl(_orchestrator(tool_context, []), io.read, io.write)

    assert io.outputs  # a goodbye was printed


def test_repl_ignores_blank_input(tool_context):
    plan = json.dumps({"summary": "Answered.", "steps": []})
    io = _Recorder(["", "   ", "hi", "/exit"])

    run_repl(_orchestrator(tool_context, [plan]), io.read, io.write)

    assert sum("Answered." in line for line in io.outputs) == 1


def test_build_orchestrator_wires_a_working_object(tmp_path):
    from nova.config import NovaConfig

    config = NovaConfig.from_env(
        {"NOVA_WORKSPACE_ROOT": str(tmp_path / "ws"), "NOVA_LLM_PROVIDER": "fake"},
        default_root=tmp_path,
    )

    orchestrator = build_orchestrator(config)

    assert isinstance(orchestrator, Orchestrator)
    assert orchestrator.history == []
