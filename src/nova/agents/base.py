"""What a NOVA specialist agent is."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Agent:
    """A specialist: a scoped tool set plus planning guidance.

    Agents do not each own a model. They narrow *which* tools the planner may
    reach for and *how* it should think about the request, which keeps the
    prompt small and makes wrong-tool mistakes structurally impossible rather
    than merely unlikely.
    """

    name: str
    description: str
    tools: tuple[str, ...]
    guidance: str
