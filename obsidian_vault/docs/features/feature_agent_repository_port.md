---
created: 2026-09-05
updated: 2026-09-06
type: spec
phase: 1
layer: domain
status: implemented
tags: [port, repository, agent, domain, interface, ai-agent-assistant]
category: meta-project
---

# Feature: Domain Port - IAgentRepository

**As a** system developer
**I want** to define the `IAgentRepository` abstract port in the Domain layer
**So that** Application use cases can persist and retrieve `Agent` entities without being coupled to any specific storage technology (SQLite, PostgreSQL, in-memory, etc.).

## Context & Motivation

Per ADR-004 (Clean Architecture), persistence is an Infrastructure detail. The Domain defines **what** repository operations are needed; the Infrastructure layer provides the **how** via concrete adapters (e.g., `InMemoryAgentRepository`, `SQLiteAgentRepository`).

## Port Contract

The `IAgentRepository` interface must expose the following methods:

### `save(agent: Agent) -> None`
Persists a new agent or updates an existing one (upsert semantics).

| Constraint | Detail |
|:-----------|:-------|
| Input | A fully-valid `Agent` entity (invariants already enforced). |
| Output | `None` |
| Error | Raises `RepositoryError` if persistence fails. |

---

### `find_by_id(agent_id: UUID) -> Agent | None`
Retrieves an agent by its unique identifier.

| Constraint | Detail |
|:-----------|:-------|
| Input | A `uuid.UUID` instance. |
| Output | The matching `Agent` entity, or `None` if not found. |
| Error | Raises `RepositoryError` on storage failure. |

---

### `find_all() -> list[Agent]`
Returns all stored agents. Returns an empty list if none exist.

| Constraint | Detail |
|:-----------|:-------|
| Output | `list[Agent]` (may be empty, never `None`). |
| Error | Raises `RepositoryError` on storage failure. |

---

### `delete(agent_id: UUID) -> None`
Removes an agent by ID. Is idempotent: deleting a non-existent ID must **not** raise an error.

| Constraint | Detail |
|:-----------|:-------|
| Input | A `uuid.UUID` instance. |
| Output | `None` |
| Error | Raises `RepositoryError` on storage failure. |

## Domain Exception

`RepositoryError` lives in `src/domain/exceptions.py` alongside `LLMProviderError`. Infrastructure adapters must catch their storage-specific exceptions and re-raise as `RepositoryError`.

## Acceptance Criteria

### Scenario 1: Port is abstract — cannot be instantiated directly

```
Given the IAgentRepository class
When IAgentRepository() is instantiated directly
Then a TypeError is raised (ABC enforcement)
```

### Scenario 2: save and find_by_id round-trip

```
Given a concrete InMemoryAgentRepository
And   a valid Agent entity
When  repo.save(agent) is called
And   repo.find_by_id(agent.id) is called
Then  the returned agent equals the saved agent
```

### Scenario 3: find_by_id returns None for unknown ID

```
Given a concrete InMemoryAgentRepository with no agents
When  repo.find_by_id(some_uuid) is called
Then  None is returned
```

### Scenario 4: find_all returns empty list when no agents exist

```
Given a concrete InMemoryAgentRepository with no agents
When  repo.find_all() is called
Then  an empty list [] is returned
```

### Scenario 5: delete is idempotent

```
Given a concrete InMemoryAgentRepository with no agents
When  repo.delete(some_uuid) is called
Then  no exception is raised
```

### Scenario 6: save multiple, find_all returns all

```
Given a concrete InMemoryAgentRepository
And   two valid Agent entities saved via repo.save()
When  repo.find_all() is called
Then  a list of length 2 is returned
```

## Implementation Notes

- Use Python's `abc.ABC` + `abc.abstractmethod`. **No third-party packages in Domain.**
- Port lives at: `src/domain/ports/agent_repository.py`
- The first concrete implementation for tests will be `InMemoryAgentRepository` in `src/infrastructure/persistence/in_memory_agent_repository.py` (or in a test fixture).
- Future adapters (SQLite, PostgreSQL) implement the same port — no Application layer changes required (ADR-004).
