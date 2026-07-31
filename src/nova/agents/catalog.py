"""The specialist agents NOVA ships with."""

from __future__ import annotations

from nova.agents.base import Agent

FILE_AGENT = Agent(
    name="files",
    description="Reading, writing, organising and inspecting files and folders.",
    tools=("file_list", "file_read", "file_write"),
    guidance=(
        "Work only inside the workspace. If you are unsure what exists, list a "
        "directory before reading or writing. Never overwrite a file you have "
        "not read unless the user clearly asked to replace it."
    ),
)

SYSTEM_AGENT = Agent(
    name="system",
    description=(
        "Running commands, inspecting the machine, processes, installed tools "
        "and anything that needs a shell."
    ),
    tools=("shell_run", "file_list", "file_read"),
    guidance=(
        "Prefer a read-only inspection command over one that changes state. "
        "Run one command at a time and check its output before the next. "
        "Never chain destructive operations."
    ),
)

MEMORY_AGENT = Agent(
    name="memory",
    description=(
        "Remembering, recalling or forgetting the user's preferences, projects "
        "and standing facts."
    ),
    tools=("memory_forget", "memory_recall", "memory_remember"),
    guidance=(
        "Use short, stable, lowercase keys so the same fact overwrites rather "
        "than duplicating. Recall before you remember, to avoid storing a "
        "near-duplicate of something already known."
    ),
)

GENERAL_AGENT = Agent(
    name="general",
    description=(
        "Anything that does not clearly belong to another specialist, or that "
        "spans several of them."
    ),
    tools=(),  # empty means "every registered tool"
    guidance="Pick the least dangerous tool that accomplishes the request.",
)

AGENTS: tuple[Agent, ...] = (
    FILE_AGENT,
    SYSTEM_AGENT,
    MEMORY_AGENT,
    GENERAL_AGENT,
)

AGENTS_BY_NAME = {agent.name: agent for agent in AGENTS}
