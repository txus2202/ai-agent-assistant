"""
Domain Port: ITaskRepository

Abstract interface that decouples Application use cases from any specific
storage technology for Task persistence (ADR-004, ADR-011).
"""
from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from src.domain.entities.task import Task


@runtime_checkable
class ITaskRepository(Protocol):
    """
    Port (output) for Task persistence.

    All methods must catch adapter-specific exceptions and re-raise them as
    ``src.domain.exceptions.RepositoryError``.
    """

    def save(self, task: Task) -> None:
        """Upsert — insert or replace by ``task.id``."""
        ...

    def find_by_id(self, task_id: uuid.UUID) -> Task | None:
        """Return the task or ``None`` if not found."""
        ...

    def find_by_agent_id(self, agent_id: uuid.UUID) -> list[Task]:
        """Return all tasks assigned to the given agent (may be empty list)."""
        ...

    def find_all(self) -> list[Task]:
        """Return all stored tasks."""
        ...

    def delete(self, task_id: uuid.UUID) -> None:
        """Remove by id. Idempotent — no error if id is absent."""
        ...
