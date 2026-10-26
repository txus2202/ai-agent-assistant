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


def load_topology(path: str | Path | None = None) -> DebateTopology:
    """
    Load and validate a DebateTopology from YAML.
    The single canonical file is './topology.yaml' located at the project root.
    Can be overridden via the `path` argument or the TOPOLOGY_FILE environment variable.
    """
    import os

    target_path: Path | None = None

    if path is not None:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Topology file not found: {path}")
        target_path = p
    elif os.environ.get("TOPOLOGY_FILE"):
        p = Path(os.environ["TOPOLOGY_FILE"])
        if not p.exists():
            raise FileNotFoundError(f"Topology file specified in TOPOLOGY_FILE not found: {p}")
        target_path = p
    else:
        candidate = project_root() / "topology.yaml"
        if candidate.exists():
            target_path = candidate

    if target_path is None:
        raise FileNotFoundError(
            f"Canonical topology configuration file not found: {project_root() / 'topology.yaml'}"
        )

    content = target_path.read_text(encoding="utf-8")
    data = yaml.safe_load(content) or {}

    # Support nested phases structure if present
    if "phases" in data and isinstance(data["phases"], dict):
        phases = data["phases"]
        if "phase_1" in phases and "agent" in phases["phase_1"]:
            data.setdefault("interpreter", phases["phase_1"]["agent"])
        if "phase_2" in phases:
            p2 = phases["phase_2"]
            if "agents" in p2 and isinstance(p2["agents"], (list, tuple)):
                data.setdefault("proposers", p2["agents"])
            if "reviewer" in p2:
                data.setdefault("reviewer", p2["reviewer"])
            if "review_rounds" in p2:
                data.setdefault("review_rounds", p2["review_rounds"])
        if "phase_3" in phases and "agent" in phases["phase_3"]:
            data.setdefault("evaluator", phases["phase_3"]["agent"])
        if "phase_4" in phases and "agents" in phases["phase_4"]:
            if isinstance(phases["phase_4"]["agents"], (list, tuple)):
                data.setdefault("implementers", phases["phase_4"]["agents"])

    required_slots = ("supervisor", "interpreter", "proposers", "reviewer", "evaluator", "implementers")
    for slot in required_slots:
        if slot not in data or data[slot] is None:
            raise ValueError(f"Missing required topology slot in topology.yaml: '{slot}'")

    supervisor = str(data["supervisor"])
    interpreter = str(data["interpreter"])

    proposers_raw = data["proposers"]
    if isinstance(proposers_raw, (list, tuple)):
        proposers = tuple(str(x) for x in proposers_raw)
    else:
        proposers = (str(proposers_raw),)

    reviewer = str(data["reviewer"])
    evaluator = str(data["evaluator"])

    implementers_raw = data["implementers"]
    if isinstance(implementers_raw, (list, tuple)):
        implementers = tuple(str(x) for x in implementers_raw)
    else:
        implementers = (str(implementers_raw),)

    review_rounds = int(data.get("review_rounds", 1))

    top = DebateTopology(
        supervisor=supervisor,
        interpreter=interpreter,
        proposers=proposers,
        reviewer=reviewer,
        evaluator=evaluator,
        implementers=implementers,
        review_rounds=review_rounds,
    )
    top.validate()
    return top
