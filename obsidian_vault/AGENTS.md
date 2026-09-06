# AI Workspace Rules & Context

You are an expert programming assistant specializing in Python, Vue 3, and Clean Architecture.

## 1. Architecture Rules

- **Respect the Layers:** Never allow Domain or Application code to import Infrastructure or Presentation dependencies.
- **Dependency Inversion:** Use abstract interfaces (Protocols) in the Domain for external communication.
- **No Shortcuts:** FastAPI endpoints must only validate data, call the Use Case, and return the response.

## 2. Mandatory Workflow (SDD & TDD)

1. **Analyze the Specification:** Read the corresponding `.md` file in `docs/features/`.
2. **Write Tests First (RED):**
   - For backend (Python): Use `pytest`.
   - For frontend (Vue 3): Use `vitest` for unit/integration tests and `Playwright` for E2E tests.
3. **Write the Implementation (GREEN):** Write the minimum necessary code to make tests pass.
   - After all tests pass, update the spec's frontmatter: set `status: implemented` and update `updated:` to today's date.
4. **Refactor:** Clean code, apply strict type hints, and update `ROADMAP.md` or architecture ADRs if new patterns emerge.

## 3. Conventions

- Document complex interfaces and classes using strict docstrings, ensuring seamless integration with `mkdocstrings` for automated MkDocs generation.
- Ensure all AI orchestrations use Google ADK and follow the Supervisor pattern with Human-in-the-Loop support.
- Always use environment variables (`.env`) for secrets and paths.
- All code (classes, variables, methods) and markdown documentation must be written in English.
- Communication Language: While all codebase elements, variables, commit messages, and markdown documentation must be strictly in English, your conversational responses, explanations, and direct chat interactions with the user MUST always be in Spanish.

## 4. Tech Stack

- **Backend:** Python 3.11+, FastAPI, `pytest`, MkDocs.
- **Frontend:** Vue 3, TypeScript, `vitest`, `playwright`, VitePress.
- **AI Orchestration & RAG:** Google ADK, ChromaDB.
- **LLM:** Gemini Pro / Enterprise API (Google AI Studio & Vertex AI compatible).
- **Voice Interaction:** Whisper.cpp (STT) and Piper (TTS).

## 5. Spec Conventions (docs/features/)

### Mandatory Frontmatter

Every spec file in `docs/features/` **must** begin with the following YAML frontmatter block:

```yaml
---
created: YYYY-MM-DD      # Immutable. Set once at spec creation.
updated: YYYY-MM-DD      # Updated on every meaningful revision.
phase: <number>          # Roadmap phase this spec belongs to (e.g., 1).
layer: domain|application|infrastructure|presentation
status: draft|ready|implemented
tags: [<tag1>, <tag2>]   # Lowercase. E.g.: [entity, port, use-case, agent]
---
```

### Status Lifecycle

| Status | Meaning |
|:-------|:--------|
| `draft` | Spec is being written or is under review. Tests do not exist yet. |
| `ready` | Spec is approved and frozen. RED tests have been written and are failing. |
| `implemented` | All tests are GREEN. Production code satisfies every acceptance criterion. |

### Update Protocol (Human + Future Annotator Agent)

- **`draft` → `ready`:** Set manually when the spec is reviewed and accepted before writing tests.
- **`ready` → `implemented`:** Set immediately after all tests pass GREEN. Also update `updated:` to today's date.
- In **Phase 3+**, the **Annotator Agent** will automate this update as part of the CI/CD pipeline, removing the need for manual edits.

### Naming Convention

- File names use snake_case with a `feature_` prefix: `feature_<name>.md`.
- Dates are **not** included in file names. Use frontmatter `created` / `updated` fields instead.
- This keeps file references stable across the codebase and avoids broken links when a spec is revised.
