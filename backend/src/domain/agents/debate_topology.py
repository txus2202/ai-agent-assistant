"""
Domain: DebateTopology

Value object defining the roles and slots of agents participating in the multi-agent debate:
- supervisor: the orchestrator agent (must have is_supervisor=True)
- interpreter: initial prompt formalization agent (Phase 1)
- proposers: list of architecture proposer agents (Phase 2)
- reviewer: internal architecture peer reviewer agent (Phase 2)
- evaluator: architecture auditor and verdict agent (Phase 3)
- implementers: implementation, diagramming, and secops specialists (Phase 4)
- review_rounds: number of pre-deliberation critique iterations

All agent references are resolved dynamically via get_profile().
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import yaml

from src.domain.agents.sub_agent_profiles import get_profile, project_root


@dataclass(frozen=True)
class DebateTopology:
    """Immutable debate slot topology describing which agents fill which debate responsibilities."""

    supervisor: str
    interpreter: str
    proposers: tuple[str, ...]
    reviewer: str
    evaluator: str
    implementers: tuple[str, ...]
    review_rounds: int = 1

    def validate(self) -> None:
        """
        Validate that all agents exist in the registry and supervisor has is_supervisor=True.
        Raises KeyError if an agent cannot be resolved.
        Raises ValueError if rules are violated (e.g. non-supervisor in supervisor slot).
        """
        sup_profile = get_profile(self.supervisor)
        if not getattr(sup_profile, "is_supervisor", False):
            raise ValueError(f"Agent '{self.supervisor}' is not a valid supervisor (is_supervisor=False)")

        get_profile(self.interpreter)

        if not self.proposers or len(self.proposers) == 0:
            raise ValueError("At least one proposer agent must be defined in 'proposers'")
        for p in self.proposers:
            get_profile(p)

        get_profile(self.reviewer)
        get_profile(self.evaluator)

        for imp in self.implementers:
            get_profile(imp)

        if self.review_rounds < 0:
            raise ValueError(f"review_rounds must be >= 0, got {self.review_rounds}")


def _resolve_topology_path(path: str | Path | None = None) -> Path:
    import os

    if path is not None:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Topology file not found: {path}")
        return p

    env_path = os.environ.get("TOPOLOGY_FILE")
    if env_path:
        p = Path(env_path)
        if not p.exists():
            raise FileNotFoundError(f"Topology file specified in TOPOLOGY_FILE not found: {p}")
        return p

    candidate = project_root() / "topology.yaml"
    if candidate.exists():
        return candidate

    raise FileNotFoundError(
        f"Canonical topology configuration file not found: {candidate}"
    )


def _extract_phases_metadata(data: dict) -> None:
    phases = data.get("phases")
    if not isinstance(phases, dict):
        return

    p1 = phases.get("phase_1")
    if isinstance(p1, dict) and "agent" in p1:
        data.setdefault("interpreter", p1["agent"])

    p2 = phases.get("phase_2")
    if isinstance(p2, dict):
        if isinstance(p2.get("agents"), (list, tuple)):
            data.setdefault("proposers", p2["agents"])
        if "reviewer" in p2:
            data.setdefault("reviewer", p2["reviewer"])
        if "review_rounds" in p2:
            data.setdefault("review_rounds", p2["review_rounds"])

    p3 = phases.get("phase_3")
    if isinstance(p3, dict) and "agent" in p3:
        data.setdefault("evaluator", p3["agent"])

    p4 = phases.get("phase_4")
    if isinstance(p4, dict) and isinstance(p4.get("agents"), (list, tuple)):
        data.setdefault("implementers", p4["agents"])


def _to_string_tuple(raw_value: Any) -> tuple[str, ...]:
    if isinstance(raw_value, (list, tuple)):
        return tuple(str(x) for x in raw_value)
    return (str(raw_value),)


def load_topology(path: str | Path | None = None) -> DebateTopology:
    """
    Load and validate a DebateTopology from YAML.
    The single canonical file is './topology.yaml' located at the project root.
    Can be overridden via the `path` argument or the TOPOLOGY_FILE environment variable.
    """
    target_path = _resolve_topology_path(path)
    content = target_path.read_text(encoding="utf-8")
    data = yaml.safe_load(content) or {}

    _extract_phases_metadata(data)

    required_slots = ("supervisor", "interpreter", "proposers", "reviewer", "evaluator", "implementers")
    for slot in required_slots:
        if slot not in data or data[slot] is None:
            raise ValueError(f"Missing required topology slot in topology.yaml: '{slot}'")

    top = DebateTopology(
        supervisor=str(data["supervisor"]),
        interpreter=str(data["interpreter"]),
        proposers=_to_string_tuple(data["proposers"]),
        reviewer=str(data["reviewer"]),
        evaluator=str(data["evaluator"]),
        implementers=_to_string_tuple(data["implementers"]),
        review_rounds=int(data.get("review_rounds", 1)),
    )
    top.validate()
    return top
