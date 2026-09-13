"""
RED tests for the IAgentRepository domain port.

Spec: obsidian_vault/docs/features/feature_agent_repository_port.md
Phase: 1 | Layer: Domain

These tests validate both:
  - The abstract port contract (IAgentRepository).
  - A minimal InMemoryAgentRepository implementation used as the first
    concrete adapter (drives the TDD GREEN step for the Infrastructure layer).
"""
import uuid

import pytest

from src.domain.entities.agent import Agent, AgentStatus
from src.domain.ports.agent_repository import IAgentRepository
from src.infrastructure.persistence.in_memory_agent_repository import (
    InMemoryAgentRepository,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_agent(name: str = "Annotator") -> Agent:
    return Agent(
        name=name,
        role="Documentation specialist",
        provider="gemini",
        model_name="gemini-1.5-flash",
    )


# ---------------------------------------------------------------------------
# Scenario 1: Port is abstract — cannot be instantiated directly
# ---------------------------------------------------------------------------

def test_agent_repository_port_is_abstract() -> None:
    with pytest.raises(TypeError):
        IAgentRepository()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Scenario 2: save + find_by_id round-trip
# ---------------------------------------------------------------------------

def test_save_and_find_by_id_returns_same_agent() -> None:
    repo: IAgentRepository = InMemoryAgentRepository()
    agent = _make_agent()

    repo.save(agent)
    found = repo.find_by_id(agent.id)

    assert found is not None
    assert found.id == agent.id
    assert found.name == agent.name


# ---------------------------------------------------------------------------
# Scenario 3: find_by_id returns None for unknown ID
# ---------------------------------------------------------------------------

def test_find_by_id_returns_none_for_unknown_id() -> None:
    repo: IAgentRepository = InMemoryAgentRepository()

    result = repo.find_by_id(uuid.uuid4())

    assert result is None


# ---------------------------------------------------------------------------
# Scenario 4: find_all returns empty list when no agents exist
# ---------------------------------------------------------------------------

def test_find_all_returns_empty_list_initially() -> None:
    repo: IAgentRepository = InMemoryAgentRepository()

    result = repo.find_all()

    assert result == []


# ---------------------------------------------------------------------------
# Scenario 5: delete is idempotent (no error for non-existent ID)
# ---------------------------------------------------------------------------

def test_delete_non_existent_id_does_not_raise() -> None:
    repo: IAgentRepository = InMemoryAgentRepository()

    repo.delete(uuid.uuid4())  # must NOT raise


# ---------------------------------------------------------------------------
# Scenario 6: save multiple agents, find_all returns all
# ---------------------------------------------------------------------------

def test_find_all_returns_all_saved_agents() -> None:
    repo: IAgentRepository = InMemoryAgentRepository()
    agent_a = _make_agent(name="Annotator")
    agent_b = _make_agent(name="The Judge")

    repo.save(agent_a)
    repo.save(agent_b)
    all_agents = repo.find_all()

    assert len(all_agents) == 2
    ids = {a.id for a in all_agents}
    assert agent_a.id in ids
    assert agent_b.id in ids


# ---------------------------------------------------------------------------
# Scenario 7: save is upsert — updating an existing agent replaces it
# ---------------------------------------------------------------------------

def test_save_updates_existing_agent() -> None:
    repo: IAgentRepository = InMemoryAgentRepository()
    agent = _make_agent()
    repo.save(agent)

    # Simulate an external update by building a mutated copy
    agent.status = AgentStatus.ERROR
    repo.save(agent)

    found = repo.find_by_id(agent.id)
    assert found is not None
    assert found.status == AgentStatus.ERROR
    assert len(repo.find_all()) == 1  # still only one record


# ---------------------------------------------------------------------------
# Scenario 8: delete removes the agent; subsequent find_by_id returns None
# ---------------------------------------------------------------------------

def test_delete_removes_agent() -> None:
    repo: IAgentRepository = InMemoryAgentRepository()
    agent = _make_agent()
    repo.save(agent)

    repo.delete(agent.id)

    assert repo.find_by_id(agent.id) is None
    assert repo.find_all() == []
