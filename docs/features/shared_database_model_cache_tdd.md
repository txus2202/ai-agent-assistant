---
created: 2026-11-11
updated: 2026-11-11
type: spec
phase: 7
layer: infrastructure
status: implemented
tags: [tdd, model-cache, sqlite, lock, persistence, pytest]
---

# TDD: Test Plan for Shared Database Model Cache & Distributed Lock

## 1. Testing Strategy (Red-Green-Refactor)

Following ADR-007:
1. **RED Phase:** Write unit tests for:
   - `SqliteModelCacheRepository`:
     - Schema creation and basic `save` / `get`.
     - Invalidation when `app_version` mismatches.
     - Atomic `acquire_probe_lock` (first caller wins lock, second caller gets False until released or expired).
     - `release_probe_lock` clears probing lock.
     - `invalidate_all` removes all cached models.
   - `GET /api/models` route integration:
     - Uses `IModelCacheRepository` dependency.
     - Pod 1 acquires lock and triggers probe.
     - Simultaneous request to Pod 2 sees lock acquired and skips duplicate probe.
2. **GREEN Phase:** Implement the domain port, SQLite repository, FastAPI dependency, and route wiring.
3. **REFACTOR Phase:** Verify 100% test pass rate across backend and frontend.

---

## 2. Test Case Matrix

| ID | Layer | Test File | Scenario Description | Expected Outcome |
| :--- | :--- | :--- | :--- | :--- |
| **TC-DB-CACHE-01** | Infrastructure | `test_sqlite_model_cache_repository.py` | Save and get cached model catalog. | Returns stored models, is_verified, and timestamp. |
| **TC-DB-CACHE-02** | Infrastructure | `test_sqlite_model_cache_repository.py` | App version mismatch in `get()`. | Returns None (invalidated on new deployment). |
| **TC-DB-CACHE-03** | Infrastructure | `test_sqlite_model_cache_repository.py` | Atomic probe lock acquisition and contention. | Pod 1 acquires lock (True); Pod 2 rejected (False); after release, lock acquirable again. |
| **TC-DB-CACHE-04** | Infrastructure | `test_sqlite_model_cache_repository.py` | Expired lock takeover. | Lock older than timeout automatically reclaimed by new caller. |
| **TC-ROUTER-CACHE-01**| Presentation | `test_models.py` | Multi-pod simulation on `/api/models`. | Pod 2 does not fire duplicate probes when Pod 1 holds lock. |

---

## 3. Acceptance Criteria
1. `pytest backend/tests/` passes 100%.
2. Only 1 pod executes probes when multiple pods receive requests concurrently.
3. All pods share the same cached catalog from the database.
