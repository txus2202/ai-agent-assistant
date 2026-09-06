"""
Domain Port: IAgentRepository

Abstract interface that decouples Application use cases from any specific
storage technology (ADR-004). Concrete adapters (InMemoryAgentRepository,
SQLiteAgentRepository, etc.) must implement this contract.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from src.domain.entities.agent import Agent


class IAgentRepository(ABC):
    """
    Port (output) for Agent persistence.

    All methods that interact with storage must catch adapter-specific
    exceptions and re-raise them as ``src.domain.exceptions.RepositoryError``.
    """

    @abstractmethod
    def save(self, agent: Agent) -> None:
        """
        Persist a new Agent or update an existing one (upsert semantics).

        Args:
            agent: A fully-valid ``Agent`` entity.

        Raises:
            RepositoryError: On storage failure.
        """

    @abstractmethod
    def find_by_id(self, agent_id: uuid.UUID) -> Agent | None:
        """
        Retrieve an Agent by its unique identifier.

        Args:
            agent_id: The UUID of the agent to look up.

        Returns:
            The matching ``Agent``, or ``None`` if not found.

        Raises:
            RepositoryError: On storage failure.
        """

    @abstractmethod
    def find_all(self) -> list[Agent]:
        """
        Return all stored Agents.

        Returns:
            A (possibly empty) list of ``Agent`` instances.

        Raises:
            RepositoryError: On storage failure.
        """

    @abstractmethod
    def delete(self, agent_id: uuid.UUID) -> None:
        """
        Remove an Agent by ID. Idempotent — no error if ID does not exist.

        Args:
            agent_id: The UUID of the agent to remove.

        Raises:
            RepositoryError: On storage failure.
        """
