---
created: 2026-11-13
updated: 2026-11-13
type: spec
phase: 7
layer: testing
status: implemented
tags: [tdd, playwright, e2e, testing, test-matrix, red-green-refactor]
---

# TDD: Test-Driven Development Plan for Playwright E2E Suite

## 1. Testing Strategy (Red-Green-Refactor)

Following ADR-007 (SDD and TDD Methodology):
1. **RED Phase:** Define failing end-to-end tests across Chromium Desktop and Mobile Chrome simulating real browser sessions without an active backend, exposing missing test IDs, unhandled route guards, modal event collisions, and timing issues.
2. **GREEN Phase:** Implement the hermetic mock controller (`mockBackend.ts`), register routes with correct fallback precedence, add required `data-test` identifiers in `HistoryView.vue`, prevent duplicate keydown triggers in `PresentationModal.vue`, and ensure responsive visibility of zoom controls in `DiagramModal.vue`.
3. **REFACTOR Phase:** Validate 100% test pass rate across both browser profiles (38 test executions), verify zero regressions in Vitest unit tests (377 tests passing), ensure strict TypeScript validation (`vue-tsc --build`), and guarantee linter compliance (`oxlint`, `eslint`).

---

## 2. Test Case Matrix

| ID | Test Suite | Test Scenario Description | Expected Outcome | Desktop (Chromium) | Mobile (Pixel 7) |
| :--- | :--- | :--- | :--- | :---: | :---: |
| **TC-E2E-01** | `auth.spec.ts` | Redirect to `/setup` when backend is uninitialized (`initialized: false`) and submit admin account creation form. | User fills form, calls `/api/auth/setup`, and is redirected to `/login` with success feedback. | PASS | PASS |
| **TC-E2E-02** | `auth.spec.ts` | Attempt login with invalid credentials. | Displays error message: *"Usuario o contraseña incorrectos"*; user remains on `/login`. | PASS | PASS |
| **TC-E2E-03** | `auth.spec.ts` | Login with valid credentials (`admin` / `password123`). | Sets authentication state, creates session cookie, and navigates to `/` (dashboard). | PASS | PASS |
| **TC-E2E-04** | `auth.spec.ts` | User logout from header dropdown menu. | Calls `/api/auth/logout`, clears session state, and redirects to `/login`. | PASS | PASS |
| **TC-E2E-05** | `auth.spec.ts` | Route guard protection: attempt to navigate to `/login` when already authenticated. | Router immediately redirects back to `/`. | PASS | PASS |
| **TC-E2E-06** | `chat-and-agents.spec.ts` | Load main dashboard layout. | Header, Agent Stage (`ParticleOrb`), ChatPanel, and prompt input box are rendered and visible. | PASS | PASS |
| **TC-E2E-07** | `chat-and-agents.spec.ts` | Specialist agent dropdown selector. | Clicking selector opens menu with specialist agents (Ícaro, Hestia, Esfinge, Metis, etc.) and allows selection. | PASS | PASS |
| **TC-E2E-08** | `chat-and-agents.spec.ts` | Send user message and stream assistant response via WebSocket. | Input cleared, user bubble rendered, assistant bubble streams tokens and renders final text. | PASS | PASS |
| **TC-E2E-09** | `chat-and-agents.spec.ts` | Trigger HITL (*Human-in-the-Loop*) control point and approve proposed action. | HITL card displayed with action details; clicking "Aprobar" sends `hitl_decision` over WebSocket and updates status. | PASS | PASS |
| **TC-E2E-10** | `chat-and-agents.spec.ts` | Dynamic floating scroll button visibility. | In short chat: button is hidden. In long chat: button appears to scroll down or up depending on viewport position. | PASS | PASS |
| **TC-E2E-11** | `history.spec.ts` | Navigate to `/history` from header. | Lists archived deliberation sessions with timestamps and metadata. | PASS | PASS |
| **TC-E2E-12** | `history.spec.ts` | Real-time text search in session history. | Typing query filters the card list; non-matching sessions are hidden. | PASS | PASS |
| **TC-E2E-13** | `history.spec.ts` | Restore archived session into chat view. | Navigates to `/`, populates prior messages, and ensures HITL control points remain closed/inactive. | PASS | PASS |
| **TC-E2E-14** | `history.spec.ts` | Delete session from history. | Clicking delete button, accepting native `window.confirm` dialog removes card from list. | PASS | PASS |
| **TC-E2E-15** | `tools-modals.spec.ts` | Presentation slides viewer interaction. | Opens modal from chat card, displays `1 / 3` counter, navigates via buttons and Arrow keys, opens PPTX/HTML export menu, closes on Escape. | PASS | PASS |
| **TC-E2E-16** | `tools-modals.spec.ts` | Mermaid diagram viewer interaction. | Opens modal from chat card, renders SVG diagram, operates zoom in, zoom out, and zoom reset buttons, closes modal. | PASS | PASS |
| **TC-E2E-17** | `tools-modals.spec.ts` | Code snippet inspector interaction. | Opens code modal, displays formatted code with syntax highlighting, and provides clipboard copy button. | PASS | PASS |
| **TC-E2E-18** | `user-management.spec.ts` | Admin user creates a new account. | Admin opens user management modal, fills username/password/role, submits form, and table updates with new user. | PASS | PASS |
| **TC-E2E-19** | `user-management.spec.ts` | Privilege boundary for non-admin users. | Standard operator logs in; user management option is hidden from user menu. | PASS | PASS |

---

## 3. Acceptance Criteria & Quality Gates

1. **E2E Test Execution (`npm run test:e2e`):**
   - 38/38 tests passing across both Chromium Desktop and Mobile Chrome projects.
   - Zero test flakiness; all tests complete deterministically within standard timeouts.
2. **Unit & Component Tests (`npm run test:unit`):**
   - 377/377 Vitest unit tests passing across all 35 test files.
3. **Type Checking (`npm run type-check`):**
   - `vue-tsc --build` passes with 0 type errors.
4. **Code Quality & Linting (`npm run lint`):**
   - `oxlint` and `eslint` pass with 0 errors and 0 warnings.
5. **No Regressions in Production Build (`npm run build-only`):**
   - Production Vite bundle builds cleanly.

