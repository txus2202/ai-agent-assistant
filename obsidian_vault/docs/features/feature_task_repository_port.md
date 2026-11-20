---
created: 2026-09-06
updated: 2026-09-08
type: spec
phase: 2
layer: domain
status: implemented
tags: [port, repository, task, domain, interface, ai-agent-assistant]
category: meta-project
---

# Feature: Domain Port — ITaskRepository

**As a** system developer
**I want** to define the `ITaskRepository` abstract port in the Domain layer
**So that** Application use cases can persist and retrieve `Task` entities without being coupled to any specific storage technology.

## Context & Motivation

Phase 1 left `Task` entities in-memory (not persisted). Without persistence, task history is lost on every restart — users can't review what was executed, and future features (auditing, retry logic, HITL) have no data to work with.

Per ADR-004 (Clean Architecture), persistence is an Infrastructure detail. Per ADR-011, the default adapter for Phase 2 is `SQLiteTaskRepository`.

## Port Contract

The `ITaskRepository` interface must expose the following methods:

| Method | Signature | Description |
| :--- | :--- | :--- |
| `save` | `(task: Task) -> None` | Upsert — insert or replace by `task.id`. |
| `find_by_id` | `(task_id: UUID) -> Task \| None` | Return task or `None` if not found. |
| `find_by_agent_id` | `(agent_id: UUID) -> list[Task]` | Return all tasks for a given agent (may be empty). |
| `find_all` | `() -> list[Task]` | Return all stored tasks. |
| `delete` | `(task_id: UUID) -> None` | Idempotent delete. |

## Acceptance Criteria

### Scenario 1: Port is abstract

```
Given the ITaskRepository class
When  an attempt to instantiate it directly is made
Then  TypeError is raised
```

### Scenario 2: save + find_by_id round-trip

```
Given a Task entity
When  repo.save(task) is called
And   repo.find_by_id(task.id) is called
Then  the returned task has the same id, prompt, and status
```

### Scenario 3: find_by_id returns None for unknown ID

```
Given an empty repository
When  repo.find_by_id(uuid.uuid4()) is called
Then  None is returned
```

### Scenario 4: find_by_agent_id returns only tasks for that agent

```
Given two tasks for agent_a and one task for agent_b
When  repo.find_by_agent_id(agent_a.id) is called
Then  exactly two tasks are returned
And   both belong to agent_a
```

### Scenario 5: delete is idempotent

```
Given a repository
When  repo.delete(unknown_uuid) is called
Then  no exception is raised
```

### Scenario 6: save persists updated task status

```
Given a saved Task in PENDING status
When  task.mark_as_running() and repo.save(task) are called
And   the task is retrieved via find_by_id
Then  the retrieved task has status RUNNING
```

## Implementation Notes

- **Port file:** `src/domain/ports/task_repository.py`
- **Phase 2 concrete adapter:** `SQLiteTaskRepository` in `src/infrastructure/persistence/`
- **Test adapter:** `InMemoryTaskRepository` in `src/infrastructure/persistence/` (used only in tests and as fallback)
- Task serialization must preserve: `id`, `prompt`, `agent_id`, `status`, `result`, `created_at`, `dependencies`.
