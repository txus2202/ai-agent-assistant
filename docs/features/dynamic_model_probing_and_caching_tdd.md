---
created: 2026-11-11
updated: 2026-11-11
type: spec
phase: 7
layer: infrastructure
status: implemented
tags: [tdd, models, gemini, anthropic, openai, probing, caching, swr, stale-while-revalidate, pytest]
---

# TDD: Test Plan for Non-Blocking SWR Model Probing & Caching

## 1. Testing Strategy (Red-Green-Refactor)

Following ADR-007:
1. **RED Phase:**
   - Update tests for `GeminiAdapter`, `AnthropicAdapter`, and `OpenAIAdapter` with `probe=False` vs `probe=True`.
   - Update `test_models.py` to test the SWR non-blocking flow:
     - TC-SWR-01: Cold start returns preliminary models immediately without blocking and emits `X-Models-Probing: 1`.
     - TC-SWR-02: Background probing finishes and updates the verified cache.
     - TC-SWR-03: Stale cache returns stale models immediately and triggers background revalidation.
     - TC-SWR-04: Fresh cache returns verified models without triggering probing.
2. **GREEN Phase:**
   - Implement `probe: bool = True` in adapters.
   - Implement SWR background task in `models.py`.
   - Update frontend `configStore.loadProviders()` to silently refresh when `X-Models-Probing: 1` is detected.
3. **REFACTOR Phase:**
   - Verify 100% test pass rate on backend and frontend, with 0 lint and 0 type errors.

---

## 2. Test Case Matrix

| ID | Layer | Test File | Scenario Description | Expected Outcome |
| :--- | :--- | :--- | :--- | :--- |
| **TC-ADAPTER-PROBE-01** | Infrastructure | `test_llm_adapters.py` | `list_models(probe=False)` does not call `count_tokens` or completions. | Returns candidate models rapidly without probe. |
| **TC-ADAPTER-PROBE-02** | Infrastructure | `test_llm_adapters.py` | `list_models(probe=True)` calls probe and excludes failing/deprecated models. | Returns verified operational models. |
| **TC-SWR-01** | Presentation | `test_models.py` | Cold start on `GET /api/models`. | Returns preliminary unverified list immediately (<50ms) with `X-Models-Probing: 1`. |
| **TC-SWR-02** | Presentation | `test_models.py` | Fresh cache on `GET /api/models`. | Returns verified list with `X-Models-Probing: 0`. |
| **TC-SWR-03** | Presentation | `test_models.py` | Stale cache on `GET /api/models`. | Returns stale models immediately and triggers background revalidation. |
| **TC-FE-SWR-01** | Frontend Store | `config.spec.ts` | `loadProviders()` detects `X-Models-Probing: 1`. | Sets silent delayed re-fetch to update store once verified. |

---

## 3. Acceptance Criteria
1. `GET /api/models` never blocks the application startup (>100ms).
2. All backend and frontend unit tests pass 100%.

