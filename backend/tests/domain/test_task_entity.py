"""
RED tests for the Task domain entity.

Spec: obsidian_vault/docs/features/feature_task_entity.md
Phase: 1 | Layer: Domain
"""
import uuid
from datetime import timezone

import pytest

from src.domain.entities.task import Task, TaskStatus


# ---------------------------------------------------------------------------
# Local fixtures (task-specific)
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_task(agent_id: uuid.UUID) -> Task:
    return Task(prompt="Describe the system architecture.", agent_id=agent_id)


# ---------------------------------------------------------------------------
# Scenario 1: Create a valid Task
# ---------------------------------------------------------------------------

def test_should_create_valid_task(agent_id: uuid.UUID) -> None:
    task = Task(prompt="Describe the system architecture.", agent_id=agent_id)

    assert isinstance(task.id, uuid.UUID)
    assert task.status == TaskStatus.PENDING
    assert task.result is None
    assert task.agent_id == agent_id
    assert task.created_at.tzinfo is not None
    assert task.created_at.tzinfo == timezone.utc
    assert task.dependencies == []


# ---------------------------------------------------------------------------
# Scenario 2: Reject empty / whitespace-only prompt
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bad_prompt", ["", "   ", "\t", "\n"])
def test_should_fail_when_prompt_is_empty(agent_id: uuid.UUID, bad_prompt: str) -> None:
    with pytest.raises(ValueError, match="Prompt cannot be empty"):
        Task(prompt=bad_prompt, agent_id=agent_id)


# ---------------------------------------------------------------------------
# Scenario 3: Reject prompt exceeding max length
# ---------------------------------------------------------------------------

def test_should_fail_when_prompt_exceeds_max_length(agent_id: uuid.UUID) -> None:
    long_prompt = "x" * 10_001
    with pytest.raises(ValueError, match="Prompt exceeds maximum length"):
        Task(prompt=long_prompt, agent_id=agent_id)


def test_should_enforce_injected_max_length_without_env_lookup(agent_id: uuid.UUID) -> None:
    short_task = Task(prompt="12345", agent_id=agent_id, max_length=5)
    assert short_task.prompt == "12345"

    with pytest.raises(ValueError, match="maximum length of 5"):
        Task(prompt="123456", agent_id=agent_id, max_length=5)

    with pytest.raises(ValueError, match="positive integer"):
        Task(prompt="valid", agent_id=agent_id, max_length=0)


# ---------------------------------------------------------------------------
# Scenario 4: Valid transition PENDING → RUNNING
# ---------------------------------------------------------------------------

def test_should_transition_from_pending_to_running(valid_task: Task) -> None:
    valid_task.mark_as_running()

    assert valid_task.status == TaskStatus.RUNNING


# ---------------------------------------------------------------------------
# Scenario 5: Valid transition RUNNING → COMPLETED
# ---------------------------------------------------------------------------

def test_should_transition_from_running_to_completed(valid_task: Task) -> None:
    valid_task.mark_as_running()
    valid_task.mark_as_completed(result="The answer is 42")

    assert valid_task.status == TaskStatus.COMPLETED
    assert valid_task.result == "The answer is 42"


# ---------------------------------------------------------------------------
# Scenario 6: Valid transition RUNNING → FAILED
# ---------------------------------------------------------------------------

def test_should_transition_from_running_to_failed(valid_task: Task) -> None:
    valid_task.mark_as_running()
    valid_task.mark_as_failed(reason="Model timeout")

    assert valid_task.status == TaskStatus.FAILED
    assert valid_task.result == "Model timeout"


# ---------------------------------------------------------------------------
# Scenario 7: Reject invalid state transition
# ---------------------------------------------------------------------------

def test_should_fail_on_invalid_transition_completed_to_running(valid_task: Task) -> None:
    valid_task.mark_as_running()
    valid_task.mark_as_completed(result="Done")

    with pytest.raises(ValueError, match="Cannot transition"):
        valid_task.mark_as_running()


def test_should_fail_on_invalid_transition_pending_to_completed(valid_task: Task) -> None:
    with pytest.raises(ValueError, match="Cannot transition"):
        valid_task.mark_as_completed(result="Skipped RUNNING")


def test_should_fail_on_invalid_transition_failed_to_completed(valid_task: Task) -> None:
    valid_task.mark_as_running()
    valid_task.mark_as_failed(reason="Error")

    with pytest.raises(ValueError, match="Cannot transition"):
        valid_task.mark_as_completed(result="Too late")


# ---------------------------------------------------------------------------
# Scenario 8: dependencies field accepts a list of UUIDs
# ---------------------------------------------------------------------------

def test_should_create_task_with_dependencies(agent_id: uuid.UUID) -> None:
    dep_id_1 = uuid.uuid4()
    dep_id_2 = uuid.uuid4()

    task = Task(
        prompt="Generate diagram.",
        agent_id=agent_id,
        dependencies=[dep_id_1, dep_id_2],
    )

    assert task.dependencies == [dep_id_1, dep_id_2]
