"""
Domain Value Object: UserTopologyConfig

Immutable per-operator customization of the multi-agent debate phase slots and
peer-review loop count. Intentionally omits ``supervisor`` so the strategic
orchestrator defined in ``topology.yaml`` remains strictly immutable.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UserTopologyConfig:
    """Immutable per-user override for debate phase specialist sets and review rounds."""

    user_id: str
    interpreters: tuple[str, ...] = ()
    proposers: tuple[str, ...] = ()
    reviewers: tuple[str, ...] = ()
    evaluators: tuple[str, ...] = ()
    implementers: tuple[str, ...] = ()
    review_rounds: int = 1

