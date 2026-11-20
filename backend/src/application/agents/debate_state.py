"""
Application Agent State: DebateState & Shared Stage Markers

Holds mutable per-debate execution state keyed dynamically by agent display names
and profile IDs without coupling to concrete council rosters.
"""
from __future__ import annotations

from typing import Any

SECTION_SEPARATOR = "\n\n---\n\n"
ERROR_MARKER = "[Error"
FAILURE_MARKER = "[Fallo"


class DebateState:
    """Mutable state of one debate. Agent-agnostic: everything is keyed by agent name."""

    def __init__(self) -> None:
        self.agent_outputs: dict[str, str] = {}
        self.agent_metadata: dict[str, dict[str, str]] = {}
        self.formalized: str = ""
        self.selected_solutions: list[str] = []
        self.final_solutions: list[str] = []
        self.hitl2_content: str = ""
        self.target_agents: list[str] = []
        self.refinement: str = ""
        self.agent_critiques: dict[str, list[str]] = {}
        self.debate_history: list[dict[str, Any]] = []
        self.finish_early: bool = False
        self.skip_consolidation: bool = False

    def get_agent_critiques(self, agent_name: str) -> list[str]:
        return self.agent_critiques.get(agent_name, [])

    def add_agent_critique(self, agent_name: str, critique: str) -> None:
        self.agent_critiques.setdefault(agent_name, []).append(critique)

