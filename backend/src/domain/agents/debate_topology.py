"""
Domain: DebateTopology Value Object

Pure immutable value object defining the roles and slots of agents participating
in the multi-agent debate:
  - supervisor: the orchestrator agent (must have is_supervisor=True)
  - interpreters: initial prompt formalization agents (Phase 1)
  - proposers: list of proposer agents (Phase 2)
  - reviewers: internal peer reviewer agents (Phase 2)
  - evaluators: auditor and verdict agents (Phase 3)
  - implementers: implementation specialists (Phase 4)
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.domain.agents.sub_agent_profiles import SubAgentProfile, resolve_profile

if TYPE_CHECKING:
    from src.domain.ports.agent_catalog_repository import IAgentCatalogRepository


@dataclass(frozen=True)
class DebateTopology:
    """Immutable debate slot topology describing which agents fill which debate responsibilities."""

    supervisor: str
    interpreters: tuple[str, ...] = ()
    proposers: tuple[str, ...] = ()
    reviewers: tuple[str, ...] = ()
    evaluators: tuple[str, ...] = ()
    implementers: tuple[str, ...] = ()
    project_name: str = "A.T.E.N.E.A."
    project_description: str = "Asistente Técnica y Evaluadora de Nuevas Estructuras y Arquitecturas"

    def validate(
        self,
        catalog: IAgentCatalogRepository | Sequence[SubAgentProfile],
    ) -> None:
        """
        Validate that all agents exist in the provided catalog and supervisor has is_supervisor=True.

        Raises KeyError if an agent cannot be resolved.
        Raises ValueError if rules are violated (e.g. non-supervisor in supervisor slot).
        """
        resolve: Callable[[str], SubAgentProfile]
        if isinstance(catalog, Sequence):
            seq_catalog = catalog

            def _resolve_seq(ident: str) -> SubAgentProfile:
                return resolve_profile(ident, seq_catalog)

            resolve = _resolve_seq
        else:
            repo_catalog = catalog
            resolve = repo_catalog.get_profile

        sup_profile = resolve(self.supervisor)
        if not getattr(sup_profile, "is_supervisor", False):
            raise ValueError(f"Agent '{self.supervisor}' is not a valid supervisor (is_supervisor=False)")

        for role_agents in (
            self.interpreters,
            self.proposers,
            self.reviewers,
            self.evaluators,
            self.implementers,
        ):
            for agent_name in role_agents:
                resolve(agent_name)
