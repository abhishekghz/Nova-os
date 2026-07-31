"""Chooses which specialist handles a request."""

from __future__ import annotations

import re

from nova.agents.base import Agent
from nova.agents.catalog import AGENTS, GENERAL_AGENT
from nova.audit import AuditLog
from nova.llm.base import LLMProvider, Message

ROUTER_SYSTEM_PROMPT = """You route requests to the right specialist.

Specialists:
{agents}

Reply with the specialist's name and nothing else. If the request spans several
specialists, or fits none of them cleanly, reply "general".
"""

_WORD = re.compile(r"[a-z]+")


class AgentRouter:
    """Picks an Agent for a message, falling back to `general` on any doubt."""

    def __init__(
        self,
        provider: LLMProvider,
        audit: AuditLog,
        agents: tuple[Agent, ...] = AGENTS,
        fallback: Agent = GENERAL_AGENT,
    ) -> None:
        self._provider = provider
        self._audit = audit
        self._agents = agents
        self._fallback = fallback
        self._by_name = {a.name: a for a in agents}

    def route(self, user_message: str, history: list[Message]) -> Agent:
        system = ROUTER_SYSTEM_PROMPT.format(agents=self._describe())
        raw = self._provider.complete(system, [Message("user", user_message)])
        agent = self._match(raw)
        self._audit.record(
            "agent_selected",
            {"message": user_message, "raw": raw.strip(), "agent": agent.name},
        )
        return agent

    def _describe(self) -> str:
        return "\n".join(f"- {a.name}: {a.description}" for a in self._agents)

    def _match(self, raw: str) -> Agent:
        """Find a known agent name in the reply. Unrecognised replies fall back."""
        for word in _WORD.findall(raw.lower()):
            if word in self._by_name:
                return self._by_name[word]
        return self._fallback
