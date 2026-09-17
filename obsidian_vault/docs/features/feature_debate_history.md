---
created: 2026-09-17
updated: 2026-09-17
type: spec
phase: 4
layer: infrastructure
status: draft
tags: [history, sqlite, debates, persistence, cleanup]
---

# Feature: Debate History Persistence

**As a** user
**I want** to browse past debates and delete old ones by date
**So that** I can revisit previous architectural discussions and keep my history clean.

## Context & Motivation

Every completed debate (DONE event) is saved to SQLite — the same database already used for Agent and Task repositories (ADR-011). No new infrastructure needed.

## Data Model

```sql
CREATE TABLE debates (
    id          TEXT PRIMARY KEY,          -- UUID v4
    created_at  TEXT NOT NULL,             -- ISO 8601 UTC, e.g. "2026-09-17T09:00:00Z"
    user_request TEXT NOT NULL,            -- original user question
    provider    TEXT NOT NULL,             -- "gemini" | "openai" | "anthropic"
    model_name  TEXT NOT NULL,             -- e.g. "gemini-1.5-flash"
    events_json TEXT NOT NULL,             -- JSON array of all SupervisorEvents
    consolidated_response TEXT NOT NULL   -- content of the DONE event
);
```

## Repository Port

```python
class IDebateRepository(ABC):
    @abstractmethod
    def save(self, debate: DebateRecord) -> None: ...

    @abstractmethod
    def list(self, limit: int = 50) -> list[DebateRecord]: ...

    @abstractmethod
    def delete_before(self, date: date) -> int: ...  # returns count deleted
```

`DebateRecord` is a domain value object:

```python
@dataclass(frozen=True)
class DebateRecord:
    id: str
    created_at: datetime
    user_request: str
    provider: str
    model_name: str
    events: list[dict]           # serialized SupervisorEvents
    consolidated_response: str
```

## REST Endpoints

### `GET /debates`

```
Query params:
  limit (int, default 50)  — max records returned

Response 200:
[
  {
    "id": "uuid",
    "created_at": "2026-09-17T09:00:00Z",
    "user_request": "Design a caching strategy",
    "provider": "gemini",
    "model_name": "gemini-1.5-flash",
    "consolidated_response": "# Executive Summary..."
  },
  ...
]
```

### `DELETE /debates`

```
Query params:
  before (str, required) — ISO date "YYYY-MM-DD"
  Deletes all debates with created_at < before (date, inclusive of that day boundary)

Response 200:
{ "deleted": 12 }

Response 400:
{ "detail": "Invalid date format. Use YYYY-MM-DD." }
```

### `GET /debates/{debate_id}`

```
Response 200: Full DebateRecord including events array
Response 404: { "detail": "Debate not found." }
```

## Acceptance Criteria

### Scenario 1: Debate saved on DONE event

```
Given a WebSocket debate completes with a DONE event
When the WebSocket handler receives the DONE event
Then a DebateRecord is inserted into SQLite
And GET /debates returns it in the list
```

### Scenario 2: List returns most recent first

```
Given 3 debates in the database
When GET /debates is called
Then response is sorted by created_at DESC
```

### Scenario 3: Delete before date removes only old debates

```
Given debates on 2026-09-10, 2026-09-15, 2026-09-17
When DELETE /debates?before=2026-09-16
Then debates from 2026-09-10 and 2026-09-15 are deleted
And debate from 2026-09-17 remains
And response is { "deleted": 2 }
```

### Scenario 4: Delete before future date with no matches

```
Given no debates older than 2026-01-01
When DELETE /debates?before=2026-01-01
Then { "deleted": 0 } is returned
And no error
```

### Scenario 5: Invalid date returns 400

```
When DELETE /debates?before=not-a-date
Then 400 { "detail": "Invalid date format. Use YYYY-MM-DD." }
```

## Implementation Notes

- `IDebateRepository` port → `src/domain/ports/debate_repository.py`
- `DebateRecord` → `src/domain/value_objects/debate_record.py`
- `SQLiteDebateRepository` → `src/infrastructure/persistence/sqlite_debate_repository.py`
- `InMemoryDebateRepository` (test double) → `src/infrastructure/persistence/in_memory_debate_repository.py`
- History routes → `src/presentation/api/routes/history.py`
- Schema migration: `debates` table created in the same `lifespan` startup hook as other tables
- The `events_json` column stores `json.dumps([event_to_dict(e) for e in events])`
