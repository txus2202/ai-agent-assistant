"""
Shared test fixtures for the ai-agent-assistant backend test suite.

Fixtures defined here are automatically available to all test modules
without explicit imports, per pytest's conftest.py discovery mechanism.

For shared test doubles (LLM adapters etc.), import from tests.doubles.
"""
import uuid

import pytest

from src.domain.entities.agent import Agent
from src.infrastructure.persistence.in_memory_agent_repository import (
    InMemoryAgentRepository,
)


# ---------------------------------------------------------------------------
# Reusable entity factory (plain function — import explicitly when needed)
# ---------------------------------------------------------------------------

def make_agent(
    name: str = "Annotator",
    role: str = "Documentation specialist",
    provider: str = "fake",
    model_name: str = "fake-v1",
) -> Agent:
    """Create a valid Agent with sensible defaults for tests."""
    return Agent(name=name, role=role, provider=provider, model_name=model_name)


# ---------------------------------------------------------------------------
# Pytest fixtures (auto-discovered — no import needed in test files)
# ---------------------------------------------------------------------------

@pytest.fixture
def agent_id() -> uuid.UUID:
    """A random UUID for use as an agent identifier in tests."""
    return uuid.uuid4()


@pytest.fixture
def sample_agent() -> Agent:
    """A pre-built valid Agent with fake provider defaults."""
    return make_agent()


@pytest.fixture
def empty_agent_repo() -> InMemoryAgentRepository:
    """An empty InMemoryAgentRepository."""
    return InMemoryAgentRepository()


@pytest.fixture
def populated_agent_repo(sample_agent: Agent) -> InMemoryAgentRepository:
    """An InMemoryAgentRepository with one agent already saved."""
    repo = InMemoryAgentRepository()
    repo.save(sample_agent)
    return repo
