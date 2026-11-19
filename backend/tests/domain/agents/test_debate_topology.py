"""
Pure unit tests for DebateTopology value object and validation.

Layer: Domain (src.domain.agents.debate_topology) — zero YAML/disk I/O.
"""
from __future__ import annotations

import pytest

from src.domain.agents.debate_topology import DebateTopology
from src.domain.agents.sub_agent_profiles import SubAgentProfile
from src.infrastructure.config.yaml_agent_catalog import InMemoryAgentCatalogRepository


def _agent(agent_id: str, name: str, *, supervisor: bool = False) -> SubAgentProfile:
    return SubAgentProfile(
        id=agent_id,
        display_name=name,
        description=f"Generic test agent {name} for topology tests.",
        color_hex="#112233",
        system_prompt=f"You are {name}. " + "Generic instructions. " * 5,
        is_supervisor=supervisor,
    )


@pytest.fixture
def generic_catalog() -> InMemoryAgentCatalogRepository:
    profiles = [
        _agent("boss", "Boss", supervisor=True),
        _agent("reader", "Reader"),
        _agent("maker_a", "MakerA"),
        _agent("maker_b", "MakerB"),
        _agent("checker", "Checker"),
        _agent("doer_a", "DoerA"),
        _agent("doer_b", "DoerB"),
    ]
    return InMemoryAgentCatalogRepository(profiles=profiles)


def _topology(**overrides) -> DebateTopology:
    values = {
        "supervisor": "Boss",
        "interpreters": ("Reader",),
        "proposers": ("MakerA", "MakerB"),
        "reviewers": ("Checker",),
        "evaluators": ("Checker",),
        "implementers": ("DoerA", "DoerB"),
    }
    values.update(overrides)
    return DebateTopology(**values)


def test_valid_topology_instantiation_and_validation(generic_catalog: InMemoryAgentCatalogRepository):
    top = _topology()
    assert top.supervisor == "Boss"
    assert top.interpreters == ("Reader",)
    assert top.proposers == ("MakerA", "MakerB")
    assert top.reviewers == ("Checker",)
    assert top.evaluators == ("Checker",)
    assert top.implementers == ("DoerA", "DoerB")
    top.validate(generic_catalog)
    top.validate(generic_catalog.get_all_profiles())


def test_topology_allows_empty_optional_roles(generic_catalog: InMemoryAgentCatalogRepository):
    top = DebateTopology(
        supervisor="Boss",
        interpreters=(),
        proposers=(),
        reviewers=(),
        evaluators=(),
        implementers=(),
    )
    top.validate(generic_catalog)
    assert top.interpreters == ()
    assert top.proposers == ()


def test_topology_is_frozen_immutable():
    top = _topology()
    with pytest.raises((AttributeError, TypeError)):
        top.supervisor = "Other"  # type: ignore[misc]


def test_validation_fails_if_supervisor_is_not_marked_is_supervisor(
    generic_catalog: InMemoryAgentCatalogRepository,
):
    top = _topology(supervisor="Reader")
    with pytest.raises(ValueError, match="not a valid supervisor"):
        top.validate(generic_catalog)


def test_validation_fails_if_agent_does_not_exist(generic_catalog: InMemoryAgentCatalogRepository):
    top = _topology(interpreters=("NonExistentAgent999",))
    with pytest.raises(KeyError):
        top.validate(generic_catalog)


def test_validation_accepts_agents_added_at_runtime(generic_catalog: InMemoryAgentCatalogRepository):
    generic_catalog.register_profile(_agent("maker_c", "MakerC"))
    _topology(proposers=("MakerA", "MakerB", "MakerC")).validate(generic_catalog)
