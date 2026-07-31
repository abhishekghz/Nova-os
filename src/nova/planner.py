"""Turns a natural-language request into a validated tool-call plan."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from nova.llm.base import LLMProvider, Message
from nova.memory.store import MemoryStore
from nova.tools.registry import ToolRegistry, UnknownToolError

PLANNER_SYSTEM_PROMPT = """You are the planner for NOVA, a personal AI operating system.

Turn the user's latest message into a short plan of tool calls.

Available tools:
{tools}

What you already know about this user (from long-term memory):
{memory}

Rules:
- Reply with a single JSON object and nothing else.
- Shape: {{"summary": "<one sentence>", "steps": [{{"tool": "<name>", \
"arguments": {{...}}, "rationale": "<why>"}}]}}
- Use at most {max_steps} steps.
- Only use tools from the list above, with arguments matching their schema.
- If the message needs no tools (a greeting, a question you can answer directly),
  return an empty "steps" array and put your answer in "summary".
- Prefer the least dangerous tool that does the job. Never invent file paths;
  list a directory first if you are unsure what exists.
- Use what you already know instead of asking again. If the user tells you a
  durable preference, project or fact, save it with memory_remember.
"""

NO_MEMORY_PLACEHOLDER = "(nothing relevant remembered)"

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


class PlanParseError(Exception):
    """Raised when the model's output is not a usable plan."""


@dataclass(frozen=True)
class PlanStep:
    """A single tool call the orchestrator should attempt."""

    tool: str
    arguments: dict
    rationale: str


@dataclass(frozen=True)
class Plan:
    """What NOVA intends to do this turn."""

    summary: str
    steps: list[PlanStep]


def _extract_json(text: str) -> str:
    match = _FENCE.search(text)
    if match:
        return match.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        return text[start : end + 1]
    return text


class Planner:
    """Asks the model for a plan and validates it against the registry."""

    def __init__(
        self,
        provider: LLMProvider,
        registry: ToolRegistry,
        max_steps: int,
        memory: MemoryStore | None = None,
    ) -> None:
        self._provider = provider
        self._registry = registry
        self._max_steps = max_steps
        self._memory = memory

    def plan(self, user_message: str, history: list[Message]) -> Plan:
        system = PLANNER_SYSTEM_PROMPT.format(
            tools=self._registry.describe_for_prompt(),
            memory=self._recalled(user_message),
            max_steps=self._max_steps,
        )
        messages = [*history, Message("user", user_message)]
        raw = self._provider.complete(system, messages)
        return self._parse(raw)

    def _recalled(self, user_message: str) -> str:
        """Long-term memory relevant to this message, rendered for the prompt."""
        if self._memory is None:
            return NO_MEMORY_PLACEHOLDER
        return self._memory.describe_for_prompt(user_message) or NO_MEMORY_PLACEHOLDER

    def _parse(self, raw: str) -> Plan:
        try:
            payload = json.loads(_extract_json(raw))
        except json.JSONDecodeError as exc:
            raise PlanParseError(f"planner output was not valid JSON: {exc}") from exc

        if not isinstance(payload, dict):
            raise PlanParseError("planner output was not a JSON object")

        raw_steps = payload.get("steps", [])
        if not isinstance(raw_steps, list):
            raise PlanParseError("'steps' must be a JSON array")
        if len(raw_steps) > self._max_steps:
            raise PlanParseError(
                f"plan has {len(raw_steps)} steps, which exceeds the limit of {self._max_steps}"
            )

        steps: list[PlanStep] = []
        for index, raw_step in enumerate(raw_steps):
            if not isinstance(raw_step, dict):
                raise PlanParseError(f"step {index} is not a JSON object")
            name = raw_step.get("tool")
            if not isinstance(name, str):
                raise PlanParseError(f"step {index} has no 'tool' name")
            try:
                self._registry.get(name)
            except UnknownToolError as exc:
                raise PlanParseError(str(exc)) from exc
            arguments = raw_step.get("arguments", {})
            if not isinstance(arguments, dict):
                raise PlanParseError(f"step {index} 'arguments' must be a JSON object")
            steps.append(
                PlanStep(
                    tool=name,
                    arguments=arguments,
                    rationale=str(raw_step.get("rationale", "")),
                )
            )

        return Plan(summary=str(payload.get("summary", "")), steps=steps)
