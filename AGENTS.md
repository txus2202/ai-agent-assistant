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
4. **Refactor:** Clean code, apply strict type hints, and update `ROADMAP.md` or architecture ADRs if new patterns emerge.

## 3. Conventions

- Document complex interfaces and classes using strict docstrings, ensuring seamless integration with `mkdocstrings` for automated MkDocs generation.
- Ensure all AI orchestrations use Google ADK and follow the Supervisor pattern with Human-in-the-Loop support.
- Always use environment variables (`.env`) for secrets and paths.
- All code (classes, variables, methods) and markdown documentation must be written in English.

## 4. Tech Stack

- **Backend:** Python 3.11+, FastAPI, `pytest`, MkDocs.
- **Frontend:** Vue 3, TypeScript, `vitest`, `playwright`, VitePress.
- **AI Orchestration & RAG:** Google ADK, ChromaDB.
- **LLM:** Gemini Pro / Enterprise API (Google AI Studio & Vertex AI compatible).
- **Voice Interaction:** Whisper.cpp (STT) and Piper (TTS).
