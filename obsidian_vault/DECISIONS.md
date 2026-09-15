# Architecture Decision Records (ADRs)

## ADR 001: Decoupled Interfaces (Backend / Frontend)

**Date:** 2026-08-21
**Context:** The system requires an interactive UI and a fast CLI.
**Decision:** Backend in FastAPI (Python) to expose input ports, and Frontend in Vue 3.
**Consequences:** Decouples the view from the logic engine, facilitating future UI replacements.

## ADR 002: Local Vector Database (ChromaDB)

**Date:** 2026-08-21
**Context:** Privacy compliance when reading local Obsidian notes.
**Decision:** Use ChromaDB running locally.
**Consequences:** Zero extra cost, 100% private.

## ADR 003: Real-Time Communication

**Date:** 2026-08-21
**Context:** AI agent debates are long-running processes.
**Decision:** Use WebSockets to stream state and tokens to Vue 3.
**Consequences:** Greatly improves UX at the cost of Presentation layer complexity.

## ADR 004: Clean Architecture Pattern

**Date:** 2026-08-21
**Context:** Future risk of changing LLM providers or tools.
**Decision:** Adopt Clean/Hexagonal Architecture. Every external service acts as an Adapter implementing a Domain Port.
**Consequences:** High resilience over time, but increases boilerplate code initially.

## ADR 005: Agent Orchestration (Google ADK)

**Date:** 2026-08-21
**Context:** A framework is needed to orchestrate the Supervisor agent pattern.
**Decision:** Use Google ADK over LangChain or CrewAI.
**Consequences:** Native, code-first integration with Gemini Enterprise with minimal abstraction overhead.

## ADR 006: Voice Interaction Privacy

**Date:** 2026-08-21
**Context:** The system requires voice control (TTS/STT) without sending audio to external servers.
**Decision:** Implement open-source local models in the Infrastructure layer: Whisper.cpp for STT and Piper for TTS.
**Consequences:** Guarantees 100% audio privacy, slightly increases local CPU usage during voice processing.

## ADR 007: SDD and TDD Methodology

**Date:** 2026-08-21
**Context:** Guarantee quality and maintainability from day one.
**Decision:** Development driven by specifications in `docs/features/`, writing tests before implementation.

## ADR 008: Automated Documentation Strategy

**Date:** 2026-09-04
**Context:** The system requires comprehensive, low-maintenance documentation that aligns with the Markdown/Obsidian ecosystem.
**Decision:** Utilize FastAPI's native OpenAPI for REST endpoints, MkDocs (Material) with `mkdocstrings` for backend logic and architectural records, and VitePress for the frontend.
**Consequences:** Keeps all documentation in Markdown format, allowing the Annotator Agent to update documentation directly while enabling developers to auto-generate code references.

## ADR 009: Dual LLM API Support (AI Studio vs Vertex AI)

**Date:** 2026-09-04
**Context:** The system must be accessible for individual development while supporting strict corporate privacy requirements.
**Decision:** The Infrastructure layer must support both Google AI Studio (Gemini Pro) for individual users and Vertex AI (Gemini Enterprise) for corporate deployments.
**Consequences:** Requires clear documentation warning users that the free tier of AI Studio does not guarantee data privacy, while the architecture remains robust enough to swap endpoints via `.env` variables for Enterprise environments.

## ADR 010: Multi-Provider LLM & User-Defined Routing

**Date:** 2026-09-05
**Context:** Different tasks require different levels of reasoning, and users may prefer different LLM ecosystems (OpenAI, Anthropic, Google) depending on their available budgets and keys.
**Decision:** The Domain `Agent` entity will hold `provider` and `model_name` as string fields dynamically configured by the user. The Application layer will route the prompt accordingly.
**Consequences:** Gives the user absolute control over API costs and privacy tiers, though it requires building an initial settings interface in the UI to map agents to models.

## ADR 011: SQLite as Persistent Storage for Domain Entities

**Date:** 2026-09-06
**Context:** Phase 1 uses `InMemoryAgentRepository` for tests and development. However, an end-user running the application locally needs `Agent` configurations and `Task` history to survive process restarts. ChromaDB (ADR-002) is exclusively for vector embeddings (RAG over Obsidian notes) and is not a substitute for structured entity storage. No persistent adapter for domain entities was explicitly planned in the initial roadmap — this is a gap detected during Phase 1 implementation.
**Decision:** Implement `SQLiteAgentRepository` and `SQLiteTaskRepository` in Phase 2 as the default persistent adapters for local execution. The `sqlite3` standard library module will be used directly to keep the dependency footprint at zero. The database file will be stored at a user-configurable path via the `DB_PATH` environment variable, defaulting to `~/.ai-agent-assistant/data.db`.
**Consequences:**
- Agent and Task data persists across sessions with no external server required.
- Aligns with the local-first, privacy-first philosophy (ADR-002).
- Swapping to PostgreSQL in a future multi-user deployment requires only a new Infrastructure adapter — Domain and Application layers remain untouched (ADR-004).
- Introduces a DB schema migration concern; a minimal migration strategy (e.g., versioned `CREATE TABLE IF NOT EXISTS`) must be defined in Phase 2.

## ADR 012: RAG Pipeline Architecture — Chunking, Embedding and Document Store Strategy

**Date:** 2026-09-08
**Context:** Phase 2 requires building a Retrieval-Augmented Generation (RAG) pipeline to allow ATENEA agents to query the Obsidian knowledge vault semantically. Three decisions must be fixed before implementation: (1) embedding model, (2) chunking strategy, and (3) ChromaDB collection schema. An additional design constraint emerged: the vault will grow well beyond project specs and ADRs — a future Apprentice/Learning Agent will generate `.md` files from external sources (PDFs, images, web URLs), triggering the same ingestion pipeline. The chunking and embedding strategy must be generic enough to handle heterogeneous document types.
**Decisions:**
1. **Embedding model: sentence-transformers `all-MiniLM-L6-v2` (local, via ChromaDB default).** Requires no external API key, runs entirely on-device, and aligns with ADR-002 (local-first, privacy-first). Can be swapped for a higher-quality API-based model (e.g., `text-embedding-004`) in Phase 4+ via the `IDocumentStore` port without touching business logic.
2. **Chunking strategy: section-based (H2/H3 boundaries).** Each Markdown document is split at H2/H3 headers; each resulting section becomes one ChromaDB document. YAML frontmatter is parsed as metadata (not embedded as text), enabling precise `where`-clause filters (e.g., `{"type": "spec", "status": "implemented"}`). This strategy is generic enough for any well-structured `.md` file, regardless of origin.
3. **ChromaDB collection: single collection `vault_docs`.** One collection with rich metadata per chunk (`type`, `phase`, `layer`, `status`, `tags`, `file_path`, `heading`). Multi-collection architecture is deferred until volume justifies it.
4. **Ingestion trigger: manual CLI script in Phase 2.** File-system watching (inotify/FSEvents) and git hooks are deferred to Phase 3.
**Consequences:**
- Zero API cost for the embedding step. Embedding quality is good (not state-of-the-art) for technical text.
- Section-based chunks produce semantically coherent units for architecture docs. For future free-form documents (Learning Agent output), this requires generated `.md` files to use consistent H2/H3 structure.
- Metadata filtering in ChromaDB allows targeted retrieval without re-ranking (Phase 2). Cross-encoder re-ranking is deferred to Phase 4.
- The Learning Agent (Phase 3) must commit to generating `.md` files with YAML frontmatter and H2/H3 structure to be compatible with this ingestion pipeline.

## ADR 013: LLM Provider Registry Pattern

**Date:** 2026-09-15
**Context:** Phase 3 introduces three concrete LLM adapters (Gemini, OpenAI, Anthropic). The `RunAgentTask` use case already routes by `agent.provider` string (ADR-010), but needs a runtime map from that string to an `ILLMProvider` instance. The registry must live in Application, not Infrastructure, to avoid inverting the dependency direction.
**Decision:** Implement `LLMProviderRegistry` in `src/application/services/llm_provider_registry.py`. It is a mutable singleton configured at startup (e.g., in `main.py`). It raises `ProviderNotFoundError` (domain exception) for unknown provider names, keeping the error vocabulary in the domain.
**Consequences:** Adding a new LLM provider requires only a new Infrastructure adapter + one `registry.register()` call — no changes to Domain or Application business logic.

## ADR 014: Learning Agent Pipeline & Storage Convention

**Date:** 2026-09-15
**Context:** The Learning Agent generates `.md` files from external sources and must store them in a location that is (a) clearly separated from hand-written vault content, (b) automatically picked up by the ingestion pipeline, and (c) sortable by date.
**Decision:**
1. Generated files are saved to `obsidian_vault/learned/{date}_{slug}.md` — a dedicated subdirectory, never mixed with `docs/`.
2. Filename format: `YYYY-MM-DD_{slug}.md` — sortable and human-readable.
3. Image source support (via Gemini Vision or similar) is deferred to Phase 4 — Phase 3 handles PDF and URL only.
4. `PyMuPDF`, `httpx`, and `beautifulsoup4` are added to `requirements.txt`.
5. `ExtractionError` is added to `src/domain/exceptions.py` as the anti-corruption exception for extractor failures.
**Consequences:** The `learned/` directory is automatically indexed by `ingest_vault.py`. Re-learning the same source overwrites the file (same slug) and is idempotent due to ChromaDB's upsert-by-ID semantics.

## ADR 015: Supervisor Pattern, HITL Design & ADK Deferral

**Date:** 2026-09-15
**Context:** ADR-005 selected Google ADK as the orchestration framework. However, integrating ADK in Phase 3 would introduce a third-party dependency into the Application orchestration layer, complicating TDD and coupling the debate flow to a specific SDK before the core logic is validated.
**Decision:**
1. Phase 3 implements the Supervisor Agent as a pure Python generator (`Generator[SupervisorEvent, None, None]`) in the Application layer. No ADK dependency.
2. Google ADK is introduced in Phase 4 as an Infrastructure adapter that wraps the Supervisor, delegating to the same Application service. This preserves ADR-004 (Clean Architecture).
3. HITL checkpoints are modelled as synchronous `Callable[[SupervisorEvent], HITLResponse]` in Phase 3. Phase 4 replaces this with an `asyncio.Queue` or WebSocket send/receive without changing the Supervisor's internal logic.
4. The event model (`SupervisorEvent`, `EventType`, `HITLDecision`) lives in `src/domain/agents/supervisor_events.py` — it is infrastructure-agnostic.
**Consequences:** Full TDD coverage of the debate flow in Phase 3. Phase 4 ADK integration only requires a thin adapter, not a rewrite.
