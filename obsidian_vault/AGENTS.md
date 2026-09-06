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

## 5. Vault Document Conventions

### Frontmatter: Two-Level Schema

Every `.md` file created inside the vault (excluding root config files: `AGENTS.md`, `ARCHITECTURE.md`, `DECISIONS.md`, `PROJECT_CONTEXT.md`) **must** begin with a YAML frontmatter block.

The schema has two levels: **common fields** (mandatory for all) + **type-specific fields**.

#### Common Fields (all document types)

```yaml
---
created: YYYY-MM-DD      # Immutable. Set once at creation.
updated: YYYY-MM-DD      # Updated on every meaningful revision.
type: spec|adr|moc|note  # Document type — used by the Annotator Agent to build indexes.
tags: [<tag1>, <tag2>]   # Lowercase kebab-case. Describes content and domain area.
---
```

#### Type-Specific Fields

```yaml
# type: spec  (Feature specifications in docs/features/)
phase: <number>                                        # Roadmap phase (e.g., 1)
layer: domain|application|infrastructure|presentation  # Clean Architecture layer
status: draft|ready|implemented                        # Lifecycle state

# type: adr  (Architecture Decision Records)
adr_number: <number>                                   # Sequential ADR ID
decision_status: proposed|accepted|superseded|deprecated
superseded_by: <filename>                              # Only if decision_status: superseded

# type: moc  (Maps of Content — Obsidian index files)
covers: [<area1>, <area2>]                             # Domains or layers this MOC indexes

# type: note  (Session notes, research, scratch)
# No additional fields required beyond the common block.
```

### Status Lifecycle (type: spec)

| Status | Meaning |
|:-------|:--------|
| `draft` | Spec is being written or under review. Tests do not exist yet. |
| `ready` | Spec is approved and frozen. RED tests written and failing. |
| `implemented` | All tests GREEN. Production code satisfies every acceptance criterion. |

### Update Protocol (Human + Future Annotator Agent)

- **`draft` → `ready`:** Set manually when the spec is reviewed and accepted before writing tests.
- **`ready` → `implemented`:** Set immediately after all tests pass GREEN. Also update `updated:` to today's date.
- In **Phase 3+**, the **Annotator Agent** will automate this update as part of the CI/CD pipeline.

### Active Recommendation Rule

**Whenever a new `.md` file is created in the vault, the assistant must:**
1. Infer the correct `type` from the file's location and purpose.
2. Propose a fully filled frontmatter block tailored to the project context before writing any content.
3. Justify any non-obvious field choices (e.g., why a given `phase`, `layer`, or set of `tags`).

### Naming Convention

- **Specs:** `feature_<name>.md` (snake_case, `feature_` prefix).
- **ADRs:** `adr_<NNN>_<short_title>.md` (zero-padded number, e.g., `adr_011_task_persistence.md`).
- **MOCs:** `moc_<area>.md` (e.g., `moc_domain_layer.md`).
- **Notes:** `note_<YYYY-MM-DD>_<short_title>.md`.
- Dates are **never** embedded in spec or ADR filenames — use frontmatter fields instead.
