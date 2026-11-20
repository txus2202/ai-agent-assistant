---
created: 2026-11-11
updated: 2026-11-11
type: spec
phase: 7
layer: application
status: implemented
tags: [tdd, rag, chromadb, agent-config, testing, pytest, vitest]
category: meta-project
---

# TDD: Test-Driven Development Plan for Per-Agent & Per-User RAG Configuration

## 1. Testing Strategy (Red-Green-Refactor)

Following ADR-007 (SDD and TDD Methodology):
1. **RED Phase:** Define failing unit and integration tests across Domain, Infrastructure, Application, Presentation (REST/WebSocket), and Vue 3 Frontend layers for per-agent `rag_top_k` and `rag_min_score` configuration.
2. **GREEN Phase:** Implement the minimal domain value object fields, SQLite schema migration, `SubAgentRunner` / `SupervisorAgent` parameter forwarding, FastAPI validation, and `AgentCard.vue` range sliders.
3. **REFACTOR Phase:** Verify zero regressions across the backend and frontend test suites, strict type checking (`vue-tsc`), linter compliance (`oxlint`, `eslint`), and cognitive complexity limits.

---

## 2. Test Case Matrix

| ID | Layer | Test File | Scenario Description | Expected Outcome |
| :--- | :--- | :--- | :--- | :--- |
| **TC-RAG-01** | Infrastructure | `test_sqlite_agent_config_repository.py` | Persist and retrieve `rag_top_k` and `rag_min_score` isolated per `user_id`. | User 1 (`top_k=0, min_score=0.65`) and User 2 (`top_k=15, min_score=0.45`) read their own isolated values; system default remains untouched. |
| **TC-RAG-02** | Infrastructure | `test_sqlite_agent_config_repository.py` | Auto-migration of legacy `agent_configs` table lacking `rag_top_k` and `rag_min_score` columns. | `_init_schema()` adds both columns via `ALTER TABLE` without losing existing `(role, user_id, provider, model_name)` rows. |
| **TC-RAG-03** | Application | `test_sub_agent_runner.py` | `SubAgentRunner.run()` invoked with `rag_top_k=0` on a `uses_rag=True` agent. | Skips `QueryVault.run()`, returns `context_chunks=[]`, and excludes vault chunks from the LLM prompt. |
| **TC-RAG-04** | Application | `test_sub_agent_runner.py` | `SubAgentRunner.run()` invoked with custom `rag_top_k=1` and `rag_min_score=0.0`. | Forwards bounds to `QueryVault.run()` and limits `context_chunks` to at most `1` chunk. |
| **TC-RAG-05** | Application | `test_supervisor_agent.py` | `SupervisorAgent` executes a council sub-agent when `agent_config_repo` holds custom `rag_top_k` and `rag_min_score`. | `SupervisorAgent._run_DynamicNode` forwards `rag_top_k` and `rag_min_score` to `SubAgentRunner.run()`. |
| **TC-RAG-06** | Presentation | `test_config.py` | `GET /config/agents` returns default `rag_top_k` (`5`) and `rag_min_score` (`0.3`), and `PUT /config/agents/{role}` updates and preserves them across model changes. | `200 OK`; subsequent provider/model-only `PUT` preserves existing `rag_top_k` and `rag_min_score`. |
| **TC-RAG-07** | Presentation | `test_config.py` | `PUT /config/agents/{role}` rejects out-of-range `rag_top_k` (`<0` or `>50`) or `rag_min_score` (`<0.0` or `>1.0`). | Returns `422 Unprocessable Entity`. |
| **TC-RAG-08** | Frontend Store | `config.spec.ts` | `useConfigStore.updateAgentConfig` sends `rag_top_k` and `rag_min_score` in `PUT` payload and updates reactive store state. | `fetch` called with `rag_top_k` and `rag_min_score`; `store.agentsConfig` updated on `response.ok`. |
| **TC-RAG-09** | Frontend UI | `AgentCard.spec.ts` | `AgentCard.vue` hides RAG controls when `usesRag=false`, displays them when `usesRag=true`, shows `OFF` & disables proximity when `Chunks=0`, and triggers `updateAgentConfig`. | All assertions pass with `line-clamp-3` description and accessible `<label for>` bindings. |

---

## 3. Acceptance Criteria
1. All backend unit and integration tests pass (`pytest`).
2. All frontend unit tests, `vue-tsc` type checks, `oxlint`, and `eslint` checks pass with 0 errors and 0 warnings.
3. Clean Architecture boundaries (`test_decoupling_guard.py`) remain 100% intact.

