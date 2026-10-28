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
import yaml  # type: ignore[import-untyped]

from src.domain.agents.sub_agent_profiles import get_profile, project_root


@dataclass(frozen=True)
class DebateTopology:
    """Immutable debate slot topology describing which agents fill which debate responsibilities."""

    supervisor: str
    interpreters: tuple[str, ...] = ()
    proposers: tuple[str, ...] = ()
    reviewers: tuple[str, ...] = ()
    evaluators: tuple[str, ...] = ()
    implementers: tuple[str, ...] = ()

    def validate(self) -> None:
        """
        Validate that all agents exist in the registry and supervisor has is_supervisor=True.
        Raises KeyError if an agent cannot be resolved.
        Raises ValueError if rules are violated (e.g. non-supervisor in supervisor slot).
        """
        sup_profile = get_profile(self.supervisor)
        if not getattr(sup_profile, "is_supervisor", False):
            raise ValueError(f"Agent '{self.supervisor}' is not a valid supervisor (is_supervisor=False)")

        for role_agents in (self.interpreters, self.proposers, self.reviewers, self.evaluators, self.implementers):
            for agent_name in role_agents:
                get_profile(agent_name)


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


def _to_string_list(raw_value: Any) -> list[str]:
    if not raw_value:
        return []
    if isinstance(raw_value, (list, tuple)):
        return [str(x) for x in raw_value]
    return [str(raw_value)]


def load_topology(path: str | Path | None = None) -> DebateTopology:
    """
    Load and validate a DebateTopology from YAML.
    The single canonical file is './topology.yaml' located at the project root.
    Can be overridden via the `path` argument or the TOPOLOGY_FILE environment variable.
    """
    target_path = _resolve_topology_path(path)
    content = target_path.read_text(encoding="utf-8")
    data = yaml.safe_load(content) or {}

    if "supervisor" not in data or data["supervisor"] is None:
        raise ValueError("Missing required topology slot in topology.yaml: 'supervisor'")

    top = DebateTopology(
        supervisor=str(data["supervisor"]),
        interpreters=tuple(_to_string_list(data.get("interpreters"))),
        proposers=tuple(_to_string_list(data.get("proposers"))),
        reviewers=tuple(_to_string_list(data.get("reviewers"))),
        evaluators=tuple(_to_string_list(data.get("evaluators"))),
        implementers=tuple(_to_string_list(data.get("implementers"))),
    )
    top.validate()
    return top

