"""
Unit tests for UserTopologyService (Application Layer).

Covers:
  - Priority chain: User DB preference -> fallback review_rounds / topology.yaml
  - First-time user receives exact base topology + default review_rounds (is_customized=False)
  - Supervisor immutability enforcement
  - Silent auto-sanitization when an agent is removed from agents.yaml
  - Deduplication within phase slots (order-independent concurrent sets)
  - Rejection of supervisor / document-ingestion agents in phase slots
  - Rejection of empty execution phases or out-of-range review_rounds on save
  - Resetting user topology restores canonical defaults
"""
from __future__ import annotations

import pytest

from src.application.services.user_topology_service import UserTopologyService
from src.domain.agents.debate_topology import DebateTopology
from src.domain.agents.sub_agent_profiles import SubAgentProfile
from src.domain.ports.agent_catalog_repository import ITopologyProvider
from src.domain.ports.user_topology_repository import IUserTopologyRepository
from src.domain.value_objects.user_topology_config import UserTopologyConfig
from src.infrastructure.config.yaml_agent_catalog import InMemoryAgentCatalogRepository


def _profile(
    agent_id: str,
    name: str,
    *,
    supervisor: bool = False,
    can_ingest: bool = False,
) -> SubAgentProfile:
    return SubAgentProfile(
        id=agent_id,
        display_name=name,
        description=f"Generic test agent {name} description.",
        color_hex="#22ccaa",
        system_prompt=f"System instructions for {name}. " * 4,
        is_supervisor=supervisor,
        can_ingest_documents=can_ingest,
    )


class InMemoryUserTopologyRepo(IUserTopologyRepository):
    def __init__(self) -> None:
        self._store: dict[str, UserTopologyConfig] = {}

    def find_by_user_id(self, user_id: str) -> UserTopologyConfig | None:
        return self._store.get(user_id)

    def save(self, config: UserTopologyConfig) -> None:
        self._store[config.user_id] = config

    def delete_by_user_id(self, user_id: str) -> None:
        self._store.pop(user_id, None)


class StaticTopologyProvider(ITopologyProvider):
    def __init__(self, topology: DebateTopology) -> None:
        self._topology = topology

    def get_topology(self) -> DebateTopology:
        return self._topology


@pytest.fixture
def catalog() -> InMemoryAgentCatalogRepository:
    return InMemoryAgentCatalogRepository(
        profiles=[
            _profile("boss", "Boss", supervisor=True),
            _profile("reader", "Reader"),
            _profile("maker_a", "MakerA"),
            _profile("maker_b", "MakerB"),
            _profile("maker_c", "MakerC"),
            _profile("checker", "Checker"),
            _profile("doer_a", "DoerA"),
            _profile("doer_b", "DoerB"),
            _profile("ingestor", "Ingestor", can_ingest=True),
        ]
    )


@pytest.fixture
def base_topology() -> DebateTopology:
    return DebateTopology(
        supervisor="Boss",
        interpreters=("Reader",),
        proposers=("MakerA", "MakerB"),
        reviewers=("Checker",),
        evaluators=("Checker",),
        implementers=("DoerA",),
        project_name="TestProject",
        project_description="Test Description",
        review_rounds=1,
    )


@pytest.fixture
def repo() -> InMemoryUserTopologyRepo:
    return InMemoryUserTopologyRepo()


@pytest.fixture
def service(
    catalog: InMemoryAgentCatalogRepository,
    base_topology: DebateTopology,
    repo: InMemoryUserTopologyRepo,
) -> UserTopologyService:
    return UserTopologyService(
        agent_catalog=catalog,
        topology_provider=StaticTopologyProvider(base_topology),
        user_topology_repo=repo,
    )


def test_first_time_user_receives_canonical_topology_and_env_review_rounds(service: UserTopologyService):
    resolved = service.resolve_for_user("user-1", fallback_review_rounds=2)
    assert resolved.is_customized is False
    assert resolved.review_rounds == 2
    assert resolved.topology.supervisor == "Boss"
    assert resolved.topology.proposers == ("MakerA", "MakerB")
    assert resolved.topology.review_rounds == 2


def test_first_time_user_uses_topology_yaml_review_rounds_when_no_env_override(service: UserTopologyService):
    resolved = service.resolve_for_user("user-1")
    assert resolved.is_customized is False
    assert resolved.review_rounds == 1
    assert resolved.topology.review_rounds == 1


def test_user_customization_overrides_base_without_affecting_other_users(service: UserTopologyService):
    saved = service.save_for_user(
        "user-1",
        interpreters=[],
        proposers=["maker_c", "MakerB"],
        reviewers=["checker"],
        evaluators=["checker"],
        implementers=["doer_b"],
        review_rounds=3,
    )
    assert saved.is_customized is True
    assert saved.review_rounds == 3
    assert saved.topology.supervisor == "Boss"
    assert saved.topology.interpreters == ()
    assert saved.topology.proposers == ("MakerC", "MakerB")
    assert saved.topology.implementers == ("DoerB",)

    other = service.resolve_for_user("user-2", fallback_review_rounds=1)
    assert other.is_customized is False
    assert other.topology.proposers == ("MakerA", "MakerB")
    assert other.review_rounds == 1


def test_supervisor_cannot_be_modified_by_any_user(service: UserTopologyService):
    with pytest.raises(ValueError, match="Supervisor"):
        service.save_for_user(
            "user-1",
            supervisor="MakerA",
            interpreters=["Reader"],
            proposers=["MakerA"],
            reviewers=[],
            evaluators=[],
            implementers=[],
            review_rounds=1,
        )


def test_supervisor_and_ingestion_agents_rejected_in_phase_slots(service: UserTopologyService):
    with pytest.raises(ValueError, match="Supervisor"):
        service.save_for_user(
            "user-1",
            interpreters=[],
            proposers=["Boss"],
            reviewers=[],
            evaluators=[],
            implementers=[],
            review_rounds=1,
        )

    with pytest.raises(ValueError, match="Ingestor"):
        service.save_for_user(
            "user-1",
            interpreters=[],
            proposers=["Ingestor"],
            reviewers=[],
            evaluators=[],
            implementers=[],
            review_rounds=1,
        )


def test_duplicate_agents_within_same_slot_are_deduplicated(service: UserTopologyService):
    saved = service.save_for_user(
        "user-1",
        interpreters=[],
        proposers=["maker_a", "MakerA", "MakerB"],
        reviewers=["checker", "Checker"],
        evaluators=["Checker"],
        implementers=[],
        review_rounds=2,
    )
    assert saved.topology.proposers == ("MakerA", "MakerB")
    assert saved.topology.reviewers == ("Checker",)
    assert saved.topology.evaluators == ("Checker",)


def test_save_rejects_empty_all_execution_phases_or_invalid_rounds(service: UserTopologyService):
    with pytest.raises(ValueError, match="At least one specialist"):
        service.save_for_user(
            "user-1",
            interpreters=[],
            proposers=[],
            reviewers=["Checker"],
            evaluators=[],
            implementers=[],
            review_rounds=1,
        )

    with pytest.raises(ValueError, match="review_rounds"):
        service.save_for_user(
            "user-1",
            interpreters=[],
            proposers=["MakerA"],
            reviewers=[],
            evaluators=[],
            implementers=[],
            review_rounds=6,
        )


def test_auto_sanitizes_deleted_agents_from_catalog(
    service: UserTopologyService,
    catalog: InMemoryAgentCatalogRepository,
):
    service.save_for_user(
        "user-1",
        interpreters=["Reader"],
        proposers=["MakerA", "MakerC"],
        reviewers=["Checker"],
        evaluators=["Checker"],
        implementers=["DoerA", "DoerB"],
        review_rounds=2,
    )

    # Simulate MakerC and DoerB being removed from agents.yaml on a subsequent deployment
    assert catalog.unregister_profile("MakerC") is True
    assert catalog.unregister_profile("DoerB") is True

    resolved = service.resolve_for_user("user-1")
    assert resolved.is_customized is True
    assert resolved.topology.proposers == ("MakerA",)
    assert resolved.topology.implementers == ("DoerA",)
    assert resolved.review_rounds == 2


def test_reset_for_user_deletes_preference_and_restores_defaults(service: UserTopologyService):
    service.save_for_user(
        "user-1",
        interpreters=[],
        proposers=["MakerC"],
        reviewers=[],
        evaluators=[],
        implementers=[],
        review_rounds=0,
    )
    assert service.resolve_for_user("user-1").is_customized is True

    restored = service.reset_for_user("user-1", fallback_review_rounds=2)
    assert restored.is_customized is False
    assert restored.topology.proposers == ("MakerA", "MakerB")
    assert restored.review_rounds == 2

