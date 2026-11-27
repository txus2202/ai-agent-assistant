"""
Application Service: UserTopologyService

Resolves, validates, auto-sanitizes, saves, and resets per-operator debate
topology preferences while preserving strict supervisor immutability and
multi-tenant isolation.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace

from src.domain.agents.debate_topology import DebateTopology
from src.domain.agents.sub_agent_profiles import SubAgentProfile
from src.domain.ports.agent_catalog_repository import (
    IAgentCatalogRepository,
    ITopologyProvider,
)
from src.domain.ports.user_topology_repository import IUserTopologyRepository
from src.domain.value_objects.user_topology_config import UserTopologyConfig

MIN_REVIEW_ROUNDS: int = 0
MAX_REVIEW_ROUNDS: int = 5


@dataclass(frozen=True)
class ResolvedUserTopology:
    """Effective topology, review rounds, and customization state for an operator."""

    topology: DebateTopology
    review_rounds: int
    is_customized: bool


class UserTopologyService:
    """
    Coordinates hierarchical debate topology resolution and persistence.

    Resolution priority:
        1. Persisted user preference in ``IUserTopologyRepository`` (auto-sanitized).
        2. Canonical ``topology.yaml`` via ``ITopologyProvider`` (with optional
           environment ``fallback_review_rounds`` override).
    """

    def __init__(
        self,
        agent_catalog: IAgentCatalogRepository,
        topology_provider: ITopologyProvider,
        user_topology_repo: IUserTopologyRepository,
    ) -> None:
        self._agent_catalog = agent_catalog
        self._topology_provider = topology_provider
        self._user_topology_repo = user_topology_repo

    def get_eligible_profiles(self) -> list[SubAgentProfile]:
        """Return all registered specialist profiles eligible for debate phase slots."""
        return [
            profile
            for profile in self._agent_catalog.get_all_profiles()
            if not profile.is_supervisor and not profile.can_ingest_documents
        ]

    def resolve_for_user(
        self,
        user_id: str | None,
        *,
        fallback_review_rounds: int | None = None,
    ) -> ResolvedUserTopology:
        """
        Resolve the effective ``DebateTopology`` and ``review_rounds`` for ``user_id``.

        Any agent saved by the user that no longer exists in ``agent_catalog`` is
        silently stripped from its slot so catalog updates never break user sessions.
        """
        base = self._topology_provider.get_topology()
        default_rounds = self._resolve_default_rounds(base, fallback_review_rounds)

        if not user_id:
            effective_base = replace(base, review_rounds=default_rounds)
            return ResolvedUserTopology(
                topology=effective_base,
                review_rounds=default_rounds,
                is_customized=False,
            )

        saved = self._user_topology_repo.find_by_user_id(user_id)
        if saved is None:
            effective_base = replace(base, review_rounds=default_rounds)
            return ResolvedUserTopology(
                topology=effective_base,
                review_rounds=default_rounds,
                is_customized=False,
            )

        clamped_rounds = max(MIN_REVIEW_ROUNDS, min(MAX_REVIEW_ROUNDS, int(saved.review_rounds)))
        resolved_topology = DebateTopology(
            supervisor=base.supervisor,
            interpreters=self._sanitize_slot(saved.interpreters),
            proposers=self._sanitize_slot(saved.proposers),
            reviewers=self._sanitize_slot(saved.reviewers),
            evaluators=self._sanitize_slot(saved.evaluators),
            implementers=self._sanitize_slot(saved.implementers),
            project_name=base.project_name,
            project_description=base.project_description,
            review_rounds=clamped_rounds,
        )
        return ResolvedUserTopology(
            topology=resolved_topology,
            review_rounds=clamped_rounds,
            is_customized=True,
        )

    def save_for_user(
        self,
        user_id: str,
        *,
        interpreters: Sequence[str] = (),
        proposers: Sequence[str] = (),
        reviewers: Sequence[str] = (),
        evaluators: Sequence[str] = (),
        implementers: Sequence[str] = (),
        review_rounds: int = 1,
        supervisor: str | None = None,
    ) -> ResolvedUserTopology:
        """
        Validate and persist a custom topology configuration for ``user_id``.

        Raises:
            ValueError: If supervisor modification is attempted, an ineligible or
                unknown agent is supplied, ``review_rounds`` is out of bounds, or
                all execution phases are empty.
        """
        if not user_id:
            raise ValueError("user_id is required to save a user topology.")

        base = self._topology_provider.get_topology()
        self._assert_supervisor_unmodified(base.supervisor, supervisor)
        self._validate_review_rounds(review_rounds)

        clean_interpreters = self._validate_and_normalize_slot(interpreters)
        clean_proposers = self._validate_and_normalize_slot(proposers)
        clean_reviewers = self._validate_and_normalize_slot(reviewers)
        clean_evaluators = self._validate_and_normalize_slot(evaluators)
        clean_implementers = self._validate_and_normalize_slot(implementers)

        if not (clean_interpreters or clean_proposers or clean_evaluators or clean_implementers):
            raise ValueError(
                "At least one specialist agent must be assigned to an active execution phase."
            )

        config = UserTopologyConfig(
            user_id=user_id,
            interpreters=clean_interpreters,
            proposers=clean_proposers,
            reviewers=clean_reviewers,
            evaluators=clean_evaluators,
            implementers=clean_implementers,
            review_rounds=review_rounds,
        )
        self._user_topology_repo.save(config)
        return self.resolve_for_user(user_id)

    def reset_for_user(
        self,
        user_id: str,
        *,
        fallback_review_rounds: int | None = None,
    ) -> ResolvedUserTopology:
        """Delete ``user_id``'s custom topology so canonical ``topology.yaml`` defaults apply."""
        if user_id:
            self._user_topology_repo.delete_by_user_id(user_id)
        return self.resolve_for_user(user_id, fallback_review_rounds=fallback_review_rounds)

    @staticmethod
    def _resolve_default_rounds(
        base: DebateTopology,
        fallback_review_rounds: int | None,
    ) -> int:
        if fallback_review_rounds is not None:
            return max(MIN_REVIEW_ROUNDS, min(MAX_REVIEW_ROUNDS, int(fallback_review_rounds)))
        if base.review_rounds is not None:
            return max(MIN_REVIEW_ROUNDS, min(MAX_REVIEW_ROUNDS, int(base.review_rounds)))
        return 1

    def _assert_supervisor_unmodified(
        self,
        canonical_supervisor: str,
        requested_supervisor: str | None,
    ) -> None:
        if requested_supervisor is None:
            return
        canonical_profile = self._agent_catalog.get_profile(canonical_supervisor)
        try:
            requested_profile = self._agent_catalog.get_profile(requested_supervisor)
        except KeyError as exc:
            raise ValueError("Supervisor agent cannot be modified or customized.") from exc

        if requested_profile.id != canonical_profile.id:
            raise ValueError("Supervisor agent cannot be modified or customized.")

    @staticmethod
    def _validate_review_rounds(review_rounds: int) -> None:
        if isinstance(review_rounds, bool) or not (MIN_REVIEW_ROUNDS <= review_rounds <= MAX_REVIEW_ROUNDS):
            raise ValueError(
                f"review_rounds must be an integer between {MIN_REVIEW_ROUNDS} and {MAX_REVIEW_ROUNDS}."
            )

    def _validate_and_normalize_slot(self, identifiers: Sequence[str]) -> tuple[str, ...]:
        seen_ids: set[str] = set()
        normalized: list[str] = []
        for raw_ident in identifiers:
            try:
                profile = self._agent_catalog.get_profile(raw_ident)
            except KeyError as exc:
                raise ValueError(f"Unknown agent identifier: '{raw_ident}'.") from exc

            if profile.is_supervisor:
                raise ValueError("Supervisor agent cannot be assigned to debate phase slots.")
            if profile.can_ingest_documents:
                raise ValueError(
                    f"Document ingestion agent '{profile.display_name}' cannot be assigned to debate phase slots."
                )

            if profile.id not in seen_ids:
                seen_ids.add(profile.id)
                normalized.append(profile.display_name)
        return tuple(normalized)

    def _sanitize_slot(self, identifiers: Sequence[str]) -> tuple[str, ...]:
        seen_ids: set[str] = set()
        sanitized: list[str] = []
        for raw_ident in identifiers:
            try:
                profile = self._agent_catalog.get_profile(raw_ident)
            except KeyError:
                continue
            if profile.is_supervisor or profile.can_ingest_documents:
                continue
            if profile.id not in seen_ids:
                seen_ids.add(profile.id)
                sanitized.append(profile.display_name)
        return tuple(sanitized)

