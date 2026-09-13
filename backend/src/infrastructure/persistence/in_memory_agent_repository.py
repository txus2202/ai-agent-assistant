"""
Infrastructure Adapter: InMemoryAgentRepository

The simplest concrete implementation of IAgentRepository. Stores agents in
a plain Python dict keyed by UUID. Used in tests and for local CLI development
before a persistent storage adapter is introduced.
"""
from __future__ import annotations

import uuid

from src.domain.entities.agent import Agent
from src.domain.ports.agent_repository import IAgentRepository


class InMemoryAgentRepository(IAgentRepository):
    """
    In-memory implementation of ``IAgentRepository``.

    Thread-safety is not guaranteed; suitable for single-threaded test
    and CLI contexts only.
    """

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, Agent] = {}

    def save(self, agent: Agent) -> None:
        """Upsert: insert or replace the agent with matching id."""
        self._store[agent.id] = agent

    def find_by_id(self, agent_id: uuid.UUID) -> Agent | None:
        """Return the agent or None if the id is not present."""
        return self._store.get(agent_id)

    def find_all(self) -> list[Agent]:
        """Return all stored agents as a list (order not guaranteed)."""
        return list(self._store.values())

    def delete(self, agent_id: uuid.UUID) -> None:
        """Remove by id. Idempotent — no error if id is absent."""
        self._store.pop(agent_id, None)
