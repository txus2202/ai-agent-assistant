"""
Domain Port: ITaskRepository

Abstract interface that decouples Application use cases from any specific
storage technology for Task persistence (ADR-004, ADR-011).
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from src.domain.entities.task import Task


class ITaskRepository(ABC):
    """
    Port (output) for Task persistence.

    All methods must catch adapter-specific exceptions and re-raise them as
    ``src.domain.exceptions.RepositoryError``.
    """

    @abstractmethod
    def save(self, task: Task) -> None:
        """Upsert — insert or replace by ``task.id``."""

    @abstractmethod
    def find_by_id(self, task_id: uuid.UUID) -> Task | None:
        """Return the task or ``None`` if not found."""

    @abstractmethod
    def find_by_agent_id(self, agent_id: uuid.UUID) -> list[Task]:
        """Return all tasks assigned to the given agent (may be empty list)."""

    @abstractmethod
    def find_all(self) -> list[Task]:
        """Return all stored tasks."""

    @abstractmethod
    def delete(self, task_id: uuid.UUID) -> None:
        """Remove by id. Idempotent — no error if id is absent."""
