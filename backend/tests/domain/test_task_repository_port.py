"""
RED tests for the ITaskRepository domain port and InMemoryTaskRepository.

Spec: obsidian_vault/docs/features/feature_task_repository_port.md
Phase: 2 | Layer: Domain
"""
import uuid

import pytest

from src.domain.entities.task import Task
from src.domain.ports.task_repository import ITaskRepository
from src.infrastructure.persistence.in_memory_task_repository import (
    InMemoryTaskRepository,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(agent_id: uuid.UUID, prompt: str = "Explain the architecture.") -> Task:
    return Task(prompt=prompt, agent_id=agent_id)


# ---------------------------------------------------------------------------
# Scenario 1: Port is abstract — cannot be instantiated directly
# ---------------------------------------------------------------------------

def test_task_repository_port_is_abstract() -> None:
    with pytest.raises(TypeError):
        ITaskRepository()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Scenario 2: save + find_by_id round-trip
# ---------------------------------------------------------------------------

def test_save_and_find_by_id_returns_same_task(agent_id: uuid.UUID) -> None:
    repo: ITaskRepository = InMemoryTaskRepository()
    task = _make_task(agent_id)

    repo.save(task)
    found = repo.find_by_id(task.id)

    assert found is not None
    assert found.id == task.id
    assert found.prompt == task.prompt
    assert found.status == task.status


# ---------------------------------------------------------------------------
# Scenario 3: find_by_id returns None for unknown ID
# ---------------------------------------------------------------------------

def test_find_by_id_returns_none_for_unknown_id() -> None:
    repo: ITaskRepository = InMemoryTaskRepository()

    assert repo.find_by_id(uuid.uuid4()) is None


# ---------------------------------------------------------------------------
# Scenario 4: find_by_agent_id scopes correctly
# ---------------------------------------------------------------------------

def test_find_by_agent_id_returns_only_tasks_for_that_agent() -> None:
    repo: ITaskRepository = InMemoryTaskRepository()
    agent_a = uuid.uuid4()
    agent_b = uuid.uuid4()

    task_a1 = _make_task(agent_a, "Task A1")
    task_a2 = _make_task(agent_a, "Task A2")
    task_b1 = _make_task(agent_b, "Task B1")

    repo.save(task_a1)
    repo.save(task_a2)
    repo.save(task_b1)

    results = repo.find_by_agent_id(agent_a)

    assert len(results) == 2
    assert all(t.agent_id == agent_a for t in results)


def test_find_by_agent_id_returns_empty_list_when_no_tasks() -> None:
    repo: ITaskRepository = InMemoryTaskRepository()

    assert repo.find_by_agent_id(uuid.uuid4()) == []


# ---------------------------------------------------------------------------
# Scenario 5: delete is idempotent
# ---------------------------------------------------------------------------

def test_delete_non_existent_task_does_not_raise() -> None:
    repo: ITaskRepository = InMemoryTaskRepository()

    repo.delete(uuid.uuid4())  # must NOT raise


# ---------------------------------------------------------------------------
# Scenario 6: save persists updated task status (upsert semantics)
# ---------------------------------------------------------------------------

def test_save_updates_task_status(agent_id: uuid.UUID) -> None:
    repo: ITaskRepository = InMemoryTaskRepository()
    task = _make_task(agent_id)
    repo.save(task)

    task.mark_as_running()
    repo.save(task)

    found = repo.find_by_id(task.id)
    assert found is not None
    assert found.status.value == "running"
    assert len(repo.find_all()) == 1  # still one record


# ---------------------------------------------------------------------------
# Scenario extra: find_all returns all saved tasks
# ---------------------------------------------------------------------------

def test_find_all_returns_all_saved_tasks(agent_id: uuid.UUID) -> None:
    repo: ITaskRepository = InMemoryTaskRepository()
    task_1 = _make_task(agent_id, "First task")
    task_2 = _make_task(agent_id, "Second task")

    repo.save(task_1)
    repo.save(task_2)

    all_tasks = repo.find_all()
    assert len(all_tasks) == 2
