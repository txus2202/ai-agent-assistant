"""
Infrastructure Adapter: InMemoryTaskRepository

Volatile in-memory implementation of ITaskRepository.
Used in tests and as fallback when SQLite is not configured.
"""
from __future__ import annotations

import uuid

from src.domain.entities.task import Task
from src.domain.ports.task_repository import ITaskRepository


class InMemoryTaskRepository(ITaskRepository):
    """In-memory implementation of ``ITaskRepository``. Not thread-safe."""

    def __init__(self) -> None:
        self._store: dict[uuid.UUID, Task] = {}

    def save(self, task: Task) -> None:
        self._store[task.id] = task

    def find_by_id(self, task_id: uuid.UUID) -> Task | None:
        return self._store.get(task_id)

    def find_by_agent_id(self, agent_id: uuid.UUID) -> list[Task]:
        return [t for t in self._store.values() if t.agent_id == agent_id]

    def find_all(self) -> list[Task]:
        return list(self._store.values())

    def delete(self, task_id: uuid.UUID) -> None:
        self._store.pop(task_id, None)
