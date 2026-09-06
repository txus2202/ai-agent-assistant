---
created: 2026-09-05
updated: 2026-09-06
phase: 1
layer: domain
status: draft
tags: [entity, task, domain]
---

# Feature: Core Entity - Task

**As a** system developer
**I want** to define the `Task` domain entity
**So that** I can represent a discrete unit of work that can be assigned to an Agent, independently of any persistence framework.

## Business Rules (Invariant Validations)

A `Task` in our domain must contain:

- `id`: Unique identifier (UUID). Auto-generated at creation.
- `prompt`: The instruction or question sent to the Agent. Cannot be empty or whitespace. Maximum 10,000 characters.
- `status`: Current lifecycle state. Must be one of `PENDING`, `RUNNING`, `COMPLETED`, `FAILED`. Defaults to `PENDING`.
- `result`: The textual output produced by the Agent upon completion. `None` by default. Can only be set when `status` is `COMPLETED` or `FAILED`.
- `agent_id`: UUID of the Agent assigned to execute this task. Cannot be null.
- `created_at`: UTC timestamp of task creation. Auto-assigned; immutable after creation.
- `dependencies`: A list of `Task` UUIDs that must be completed before this task can start. Defaults to an empty list.

## State Transitions

Valid status transitions (enforced as domain logic):

```
PENDING  → RUNNING   (task dispatched to the agent)
RUNNING  → COMPLETED (agent returned a valid result)
RUNNING  → FAILED    (agent raised an error or timed out)
```

Any other transition (e.g., `COMPLETED → RUNNING`) must raise a `ValueError`.

## Acceptance Criteria

### Scenario 1: Create a valid Task

```
Given a valid prompt and a known agent_id
When Task() is instantiated
Then task.id is a UUID
And  task.status == TaskStatus.PENDING
And  task.result is None
And  task.created_at is a UTC datetime (timezone-aware)
```

### Scenario 2: Reject empty prompt

```
Given an empty string or whitespace-only prompt
When Task() is instantiated
Then a ValueError is raised with message "Prompt cannot be empty"
```

### Scenario 3: Reject prompt exceeding max length

```
Given a prompt longer than 10,000 characters
When Task() is instantiated
Then a ValueError is raised with message "Prompt exceeds maximum length of 10000 characters"
```

### Scenario 4: Valid state transition PENDING → RUNNING

```
Given a Task with status PENDING
When task.mark_as_running() is called
Then task.status == TaskStatus.RUNNING
```

### Scenario 5: Valid state transition RUNNING → COMPLETED

```
Given a Task with status RUNNING
When task.mark_as_completed(result="The answer is 42") is called
Then task.status == TaskStatus.COMPLETED
And  task.result == "The answer is 42"
```

### Scenario 6: Valid state transition RUNNING → FAILED

```
Given a Task with status RUNNING
When task.mark_as_failed(reason="Model timeout") is called
Then task.status == TaskStatus.FAILED
And  task.result == "Model timeout"
```

### Scenario 7: Reject invalid state transition

```
Given a Task with status COMPLETED
When task.mark_as_running() is called
Then a ValueError is raised mentioning the invalid transition
```

## Implementation Notes

- **No framework dependencies.** Pure Python 3.11+ with `datetime` from the standard library.
- The maximum prompt length must be read from the `TASK_PROMPT_MAX_LENGTH` environment variable during validation or class initialization (e.g., using `int(os.getenv("TASK_PROMPT_MAX_LENGTH", 10000))`).
- `created_at` must use `datetime.now(timezone.utc)` to guarantee timezone-awareness.
- State transition methods (`mark_as_running`, `mark_as_completed`, `mark_as_failed`) are the **only** public mutators for `status` and `result`. Direct attribute assignment from outside the entity is not enforced by Python but must be treated as a violation of invariants by callers.
- `result` is a `str | None` field; for failure cases, the error reason is stored here to keep the model simple.
