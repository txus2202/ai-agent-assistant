---
created: 2026-09-06
updated: 2026-09-06
type: spec
phase: 2
layer: infrastructure
status: draft
tags: [sqlite, repository, agent, task, infrastructure, persistence]
---

# Feature: SQLite Repositories — SQLiteAgentRepository & SQLiteTaskRepository

**As a** user running the application locally
**I want** Agent configurations and Task history to survive process restarts
**So that** I don't have to reconfigure my agent team every session.

## Context & Motivation

Phase 1 established `InMemoryAgentRepository` (volatile) as the only concrete adapter. Per ADR-011, Phase 2 introduces SQLite-backed repositories as the default for local execution.

Key constraints (ADR-011):
- Use Python stdlib `sqlite3` — zero external dependencies.
- Database path from `DB_PATH` env var, defaulting to `~/.ai-agent-assistant/data.db`.
- Schema created via `CREATE TABLE IF NOT EXISTS` (no migration framework needed in Phase 2).

## Database Schema

```sql
CREATE TABLE IF NOT EXISTS agents (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    role        TEXT NOT NULL,
    provider    TEXT NOT NULL,
    model_name  TEXT NOT NULL,
    status      TEXT NOT NULL DEFAULT 'idle'
);

CREATE TABLE IF NOT EXISTS tasks (
    id           TEXT PRIMARY KEY,
    prompt       TEXT NOT NULL,
    agent_id     TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    result       TEXT,
    created_at   TEXT NOT NULL,
    dependencies TEXT NOT NULL DEFAULT '[]'
);
```

## Acceptance Criteria

### SQLiteAgentRepository

#### Scenario 1: save + find_by_id persists to disk and survives reconnection

```
Given a SQLiteAgentRepository connected to a temp DB file
And   agent saved via repo.save(agent)
When  a NEW SQLiteAgentRepository instance opens the same file
And   find_by_id(agent.id) is called on the new instance
Then  the agent is returned with matching id, name, provider, model_name, status
```

#### Scenario 2: implements IAgentRepository (Liskov substitution)

```
Given SQLiteAgentRepository instance
When  it is assigned to a variable typed as IAgentRepository
Then  all port methods work correctly (save, find_by_id, find_all, delete)
```

#### Scenario 3: delete removes from disk

```
Given a saved agent in the SQLite DB
When  repo.delete(agent.id) is called
And   a new repo instance opens the same file
Then  find_by_id(agent.id) returns None
```

#### Scenario 4: save is upsert (update survives reconnection)

```
Given a saved agent with status IDLE
When  agent.status is changed to ERROR, repo.save(agent) called
And   a new repo instance opens the same file
Then  the retrieved agent has status ERROR
```

### SQLiteTaskRepository

#### Scenario 5: save + find_by_id persists to disk

```
Given a SQLiteTaskRepository and a Task
When  repo.save(task) is called
And   a NEW instance opens the same DB
Then  find_by_id returns the task with matching id, prompt, agent_id, status
```

#### Scenario 6: find_by_agent_id scopes correctly

```
Given three tasks: two for agent_a, one for agent_b
When  repo.find_by_agent_id(agent_a.id) is called
Then  exactly two tasks are returned, both with agent_id == agent_a.id
```

#### Scenario 7: task status and result survive reconnection

```
Given a COMPLETED task with result="answer"
When  retrieved from a new repo instance
Then  status == "completed" and result == "answer"
```

## Implementation Notes

- **Files:**
  - `src/infrastructure/persistence/sqlite_agent_repository.py`
  - `src/infrastructure/persistence/sqlite_task_repository.py`
- **Connection management:** open a connection per operation (simple, thread-safe for Phase 2) or keep a persistent connection — decide at implementation time.
- **UUID serialization:** store as `TEXT` (str representation), deserialize back to `uuid.UUID`.
- **datetime serialization:** store as ISO-8601 string (`datetime.isoformat()`), deserialize with `datetime.fromisoformat()`.
- **dependencies serialization:** store as JSON array of UUID strings (`json.dumps`/`json.loads`).
- **`DB_PATH` env var:** tests must use `tmp_path` pytest fixture to avoid writing real files.
