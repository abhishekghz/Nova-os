"""The PRD section 11 pipeline: plan, permit, execute, verify, respond."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from nova.agents.base import Agent
from nova.agents.router import AgentRouter
from nova.llm.base import LLMProvider, Message
from nova.permissions import Decision, PermissionEngine
from nova.planner import Plan, Planner, PlanParseError, PlanStep
from nova.tools.base import ToolContext, ToolResult
from nova.tools.registry import ToolRegistry

ConfirmCallback = Callable[[PlanStep], bool]

RESPONDER_SYSTEM_PROMPT = """You are NOVA, a personal AI operating system.

You have just carried out a plan on the user's computer. Below is what happened.
Write a short, direct reply to the user in plain prose:
- State what you did and what the result was.
- If a step failed or was refused, say so plainly and explain why.
- Quote concrete output when it answers the question. Do not invent results.
- No preamble, no bullet lists unless the output is genuinely a list.
"""


@dataclass(frozen=True)
class StepOutcome:
    """What happened to one planned step."""

    step: PlanStep
    decision: Decision
    result: ToolResult | None


@dataclass(frozen=True)
class TurnResult:
    """Everything produced by one user turn."""

    reply: str
    plan: Plan | None
    outcomes: list[StepOutcome]
    agent: Agent | None = None


class Orchestrator:
    """Drives one conversational turn end to end."""

    def __init__(
        self,
        planner: Planner,
        registry: ToolRegistry,
        permissions: PermissionEngine,
        provider: LLMProvider,
        context: ToolContext,
        router: AgentRouter | None = None,
    ) -> None:
        self._planner = planner
        self._registry = registry
        self._permissions = permissions
        self._provider = provider
        self._context = context
        self._router = router
        self.history: list[Message] = []

    def handle(self, user_message: str, confirm: ConfirmCallback) -> TurnResult:
        audit = self._context.audit

        agent = self._router.route(user_message, self.history) if self._router else None
        scoped = self._registry.subset(agent.tools) if agent else self._registry
        guidance = agent.guidance if agent else ""

        try:
            plan = self._planner.plan(
                user_message, self.history, registry=scoped, guidance=guidance
            )
        except PlanParseError as exc:
            audit.record("plan_failed", {"message": user_message, "error": str(exc)})
            reply = f"I could not turn that into a plan I trust. ({exc})"
            self._remember(user_message, reply)
            return TurnResult(reply=reply, plan=None, outcomes=[], agent=agent)

        audit.record(
            "plan_created",
            {
                "message": user_message,
                "agent": agent.name if agent else None,
                "summary": plan.summary,
                "steps": [{"tool": s.tool, "arguments": s.arguments} for s in plan.steps],
            },
        )

        if not plan.steps:
            reply = plan.summary
            self._remember(user_message, reply)
            return TurnResult(reply=reply, plan=plan, outcomes=[], agent=agent)

        outcomes = self._execute(plan, confirm)
        reply = self._respond(user_message, plan, outcomes)
        self._remember(user_message, reply)
        return TurnResult(reply=reply, plan=plan, outcomes=outcomes, agent=agent)

    def _execute(self, plan: Plan, confirm: ConfirmCallback) -> list[StepOutcome]:
        outcomes: list[StepOutcome] = []
        for step in plan.steps:
            spec = self._registry.get(step.tool)
            decision = self._permissions.evaluate(spec, step.arguments)

            if decision is Decision.DENY:
                outcomes.append(StepOutcome(step=step, decision=decision, result=None))
                break

            if decision is Decision.CONFIRM and not confirm(step):
                self._context.audit.record(
                    "confirmation_declined", {"tool": step.tool, "arguments": step.arguments}
                )
                outcomes.append(StepOutcome(step=step, decision=Decision.DENY, result=None))
                break

            result = spec.handler(step.arguments, self._context)
            self._context.audit.record(
                "tool_executed",
                {
                    "tool": step.tool,
                    "arguments": step.arguments,
                    "ok": result.ok,
                    "output": result.output,
                    "error": result.error,
                },
            )
            outcomes.append(StepOutcome(step=step, decision=decision, result=result))

            if not result.ok:
                break

        return outcomes

    def _respond(self, user_message: str, plan: Plan, outcomes: list[StepOutcome]) -> str:
        lines = [f"User asked: {user_message}", f"Plan: {plan.summary}", ""]
        for index, outcome in enumerate(outcomes, start=1):
            lines.append(f"Step {index}: {outcome.step.tool} {outcome.step.arguments}")
            lines.append(f"  decision: {outcome.decision.value}")
            if outcome.result is None:
                lines.append("  not executed")
            elif outcome.result.ok:
                lines.append(f"  output: {outcome.result.output}")
            else:
                lines.append(f"  failed: {outcome.result.error}")
        transcript = "\n".join(lines)
        return self._provider.complete(
            RESPONDER_SYSTEM_PROMPT, [*self.history, Message("user", transcript)]
        )

    def _remember(self, user_message: str, reply: str) -> None:
        self.history.append(Message("user", user_message))
        self.history.append(Message("assistant", reply))
