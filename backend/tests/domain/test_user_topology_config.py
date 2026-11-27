"""
Pure unit tests for UserTopologyConfig value object, IUserTopologyRepository port,
and DebateTopology review_rounds validation.

Layer: Domain
"""
from __future__ import annotations

import pytest

from src.domain.agents.debate_topology import DebateTopology
from src.domain.agents.sub_agent_profiles import SubAgentProfile
from src.domain.ports.user_topology_repository import IUserTopologyRepository
from src.domain.value_objects.user_topology_config import UserTopologyConfig
from src.infrastructure.config.yaml_agent_catalog import InMemoryAgentCatalogRepository


def _agent(agent_id: str, name: str, *, supervisor: bool = False) -> SubAgentProfile:
    return SubAgentProfile(
        id=agent_id,
        display_name=name,
        description=f"Generic test agent {name}.",
        color_hex="#112233",
        system_prompt=f"You are {name}. " + "Instructions. " * 5,
        is_supervisor=supervisor,
    )


def test_user_topology_config_is_immutable_and_has_no_supervisor_field():
    cfg = UserTopologyConfig(
        user_id="user-1",
        interpreters=("Reader",),
        proposers=("MakerA", "MakerB"),
        reviewers=("Checker",),
        evaluators=("Checker",),
        implementers=("DoerA",),
        review_rounds=2,
    )
    assert cfg.user_id == "user-1"
    assert cfg.proposers == ("MakerA", "MakerB")
    assert cfg.review_rounds == 2
    assert not hasattr(cfg, "supervisor")

    with pytest.raises((AttributeError, TypeError)):
        cfg.review_rounds = 4  # type: ignore[misc]


def test_debate_topology_validates_review_rounds_bounds():
    catalog = InMemoryAgentCatalogRepository(
        profiles=[
            _agent("boss", "Boss", supervisor=True),
            _agent("maker_a", "MakerA"),
        ]
    )

    valid_zero = DebateTopology(supervisor="Boss", proposers=("MakerA",), review_rounds=0)
    valid_zero.validate(catalog)

    valid_five = DebateTopology(supervisor="Boss", proposers=("MakerA",), review_rounds=5)
    valid_five.validate(catalog)

    invalid_negative = DebateTopology(supervisor="Boss", proposers=("MakerA",), review_rounds=-1)
    with pytest.raises(ValueError, match="review_rounds"):
        invalid_negative.validate(catalog)

    invalid_above_max = DebateTopology(supervisor="Boss", proposers=("MakerA",), review_rounds=6)
    with pytest.raises(ValueError, match="review_rounds"):
        invalid_above_max.validate(catalog)


def test_user_topology_repository_protocol_is_runtime_checkable():
    class DummyRepo:
        def find_by_user_id(self, user_id: str) -> UserTopologyConfig | None:
            return None

        def save(self, config: UserTopologyConfig) -> None:
            return None

        def delete_by_user_id(self, user_id: str) -> None:
            return None

    assert isinstance(DummyRepo(), IUserTopologyRepository)

