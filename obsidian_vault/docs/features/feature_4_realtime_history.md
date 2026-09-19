---
type: feature_spec
status: implemented
created: 2026-09-19
tags: [backend, history, realtime, phase4]
---

# Feature: Real-time Debate History Persistence

## 1. Description
Save debate sessions incrementally in real-time to SQLite, ensuring that aborted or failed sessions are not lost.

## 2. Requirements
- A `DebateRecord` must be created in SQLite upon receiving the `START` WS event.
- Every event yielded by the `SupervisorAgent` must be appended to the `events_json` column of the `DebateRecord`.
- The `status` must transition from `running` to `completed` or `aborted` based on the termination condition (DONE event or WebSocketDisconnect).
- Expose `GET /debates` and `DELETE /debates/{id}`.

## 3. Architecture
- **Domain**: `DebateRecord` entity, `IDebateRepository` port.
- **Infrastructure**: `SqliteDebateRepository` adapter.
- **Presentation**: `routes/history.py` (REST) and `routes/debate.py` (WS integration).

## 4. Test Plan (TDD)
- `test_sqlite_debate_repository.py`: Verify `create`, `append_event`, and `update_status`.
- `test_history_api.py`: Verify GET and DELETE endpoints.
- `test_debate_ws_persistence.py`: Verify WS connections correctly create and append to the repository.
