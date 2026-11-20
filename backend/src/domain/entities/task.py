"""
Domain Entity: Task

Represents a discrete unit of work assigned to an Agent. Pure Python 3.11+,
no external framework dependencies (ADR-004).

State machine:
    PENDING → RUNNING → COMPLETED
                      → FAILED
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum


# ---------------------------------------------------------------------------
# TaskStatus
# ---------------------------------------------------------------------------

class TaskStatus(Enum):
    """Lifecycle states of a Task within the system."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Valid transitions table
# ---------------------------------------------------------------------------

_VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {TaskStatus.RUNNING},
    TaskStatus.RUNNING: {TaskStatus.COMPLETED, TaskStatus.FAILED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.FAILED: set(),
}


# ---------------------------------------------------------------------------
# Task entity
# ---------------------------------------------------------------------------

class Task:
    """
    Core domain entity representing a unit of work executed by an Agent.

    Invariant validations enforced at construction time:
    - ``prompt``       : non-empty, non-whitespace; bounded by ``max_length``
                         (default 10 000).
    - ``agent_id``     : must be a valid ``uuid.UUID`` instance.
    - ``dependencies`` : list of ``uuid.UUID``; defaults to ``[]``.
    - ``status``       : initialised to ``TaskStatus.PENDING``; mutated only
                         via the public transition methods.
    - ``created_at``   : auto-assigned UTC-aware datetime; immutable.
    """

    DEFAULT_PROMPT_MAX_LENGTH = 10_000

    def __init__(
        self,
        prompt: str,
        agent_id: uuid.UUID,
        dependencies: list[uuid.UUID] | None = None,
        task_id: uuid.UUID | None = None,
        max_length: int = DEFAULT_PROMPT_MAX_LENGTH,
    ) -> None:
        self._validate_prompt(prompt, max_length=max_length)

        self.id: uuid.UUID = task_id if task_id is not None else uuid.uuid4()
        self.prompt: str = prompt
        self.agent_id: uuid.UUID = agent_id
        self.dependencies: list[uuid.UUID] = dependencies if dependencies is not None else []
        self.status: TaskStatus = TaskStatus.PENDING
        self.result: str | None = None
        self.created_at: datetime = datetime.now(timezone.utc)

    # ------------------------------------------------------------------
    # State transition methods (the ONLY public mutators for status/result)
    # ------------------------------------------------------------------

    def mark_as_running(self) -> None:
        """Transition PENDING → RUNNING."""
        self._transition_to(TaskStatus.RUNNING)

    def mark_as_completed(self, result: str) -> None:
        """Transition RUNNING → COMPLETED and store the result."""
        self._transition_to(TaskStatus.COMPLETED)
        self.result = result

    def mark_as_failed(self, reason: str) -> None:
        """Transition RUNNING → FAILED and store the failure reason."""
        self._transition_to(TaskStatus.FAILED)
        self.result = reason

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _transition_to(self, target: TaskStatus) -> None:
        allowed = _VALID_TRANSITIONS[self.status]
        if target not in allowed:
            raise ValueError(
                f"Cannot transition from {self.status.value!r} to {target.value!r}. "
                f"Allowed transitions: {[s.value for s in allowed] or 'none'}."
            )
        self.status = target

    @classmethod
    def _validate_prompt(cls, prompt: str, max_length: int = DEFAULT_PROMPT_MAX_LENGTH) -> None:
        if not isinstance(max_length, int) or isinstance(max_length, bool) or max_length <= 0:
            raise ValueError("max_length must be a positive integer.")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")
        if len(prompt) > max_length:
            raise ValueError(
                f"Prompt exceeds maximum length of {max_length} characters."
            )

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"Task(id={self.id!r}, status={self.status.value!r}, "
            f"agent_id={self.agent_id!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Task):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
