"""Permission policy: what NOVA may do without asking."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from nova.audit import AuditLog
from nova.tools.base import Risk, ToolSpec


class Decision(StrEnum):
    """Outcome of a permission check."""

    ALLOW = "allow"
    CONFIRM = "confirm"
    DENY = "deny"


@dataclass(frozen=True)
class PolicyRule:
    """Matches a tool by name and/or risk and yields a decision.

    `tool="*"` matches any tool name. `risk=None` matches any risk.
    The first matching rule in order wins.
    """

    tool: str
    risk: Risk | None
    decision: Decision


DEFAULT_POLICY: list[PolicyRule] = [
    PolicyRule(tool="*", risk=Risk.READ, decision=Decision.ALLOW),
    PolicyRule(tool="*", risk=Risk.WRITE, decision=Decision.CONFIRM),
    PolicyRule(tool="*", risk=Risk.EXECUTE, decision=Decision.CONFIRM),
]

DESTRUCTIVE_PATTERNS: list[str] = [
    r"remove-item[^\n]*-recurse",
    r"\brm\s+-[a-z]*r[a-z]*f\b",
    r"\bformat-volume\b",
    r"\bstop-computer\b",
    r"\brestart-computer\b",
    r"\bdiskpart\b",
    r"\bcipher\s+/w\b",
]

_COMPILED_DESTRUCTIVE = [re.compile(p, re.IGNORECASE) for p in DESTRUCTIVE_PATTERNS]


def _looks_destructive(arguments: dict) -> str | None:
    """Return the destructive pattern that matched these arguments, or None.

    Only applied to EXECUTE-risk tools. Applying it to every tool would refuse
    a perfectly legitimate file_write whose *content* merely mentions a
    dangerous command.
    """
    haystack = " ".join(str(v) for v in arguments.values())
    for pattern in _COMPILED_DESTRUCTIVE:
        if pattern.search(haystack):
            return pattern.pattern
    return None


class PermissionEngine:
    """Evaluates policy rules and records every decision in the audit log."""

    def __init__(self, rules: list[PolicyRule], audit: AuditLog) -> None:
        self._rules = list(rules)
        self.audit = audit

    def evaluate(self, spec: ToolSpec, arguments: dict) -> Decision:
        decision, reason = self._decide(spec, arguments)
        self.audit.record(
            "permission_decision",
            {
                "tool": spec.name,
                "risk": spec.risk.value,
                "arguments": arguments,
                "decision": decision.value,
                "reason": reason,
            },
        )
        return decision

    def _decide(self, spec: ToolSpec, arguments: dict) -> tuple[Decision, str]:
        if spec.risk is Risk.EXECUTE:
            matched = _looks_destructive(arguments)
            if matched is not None:
                return Decision.DENY, f"matched destructive pattern {matched!r}"

        for rule in self._rules:
            if rule.tool not in ("*", spec.name):
                continue
            if rule.risk is not None and rule.risk is not spec.risk:
                continue
            return rule.decision, f"rule tool={rule.tool} risk={rule.risk}"

        return Decision.DENY, "no matching policy rule"
