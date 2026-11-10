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

## ADR 016: SupervisorAgent Async Migration for WebSocket Streaming

**Date:** 2026-09-17
**Context:** Phase 3 implemented `SupervisorAgent.run()` as a synchronous generator with a synchronous `hitl_callback`. Phase 4 requires real-time WebSocket streaming and HITL via WebSocket receive — both are inherently async. Running a sync generator inside `asyncio.to_thread()` while communicating HITL decisions back via thread-safe queues is technically possible but complex and fragile.
**Decision:**

1. Convert `SupervisorAgent.run()` from `def` + `Generator` to `async def` + `AsyncGenerator`. Business logic is identical — only `yield` semantics change.
2. Convert `SubAgentRunner.run()` to `async def` accordingly.
3. The `hitl_callback` parameter type changes from `Callable[[SupervisorEvent], HITLResponse]` to `Callable[[SupervisorEvent], Awaitable[HITLResponse]]`.
4. Existing Phase 3 tests are updated: sync callbacks wrapped with `asyncio.run()` or `pytest-anyio`.
5. The WebSocket handler injects the callback directly: `async def hitl_callback(event) → HITLResponse: await ws.send_json(...); raw = await ws.receive_json(); return HITLResponse(...)`.
   **Consequences:** WebSocket handler is clean and simple. No thread pools or queues needed. Phase 3 test suite requires minor adaptation (async fixtures). The business logic itself is unchanged.

## ADR 017: Phase 4 Frontend & Backend Stack

**Date:** 2026-09-17
**Context:** Phase 4 introduces a user-facing interface. The project is local-first, Python-first, with a small team. The frontend prototype is designed in Google Stitch.
**Decision:**

1. **Frontend:** Vue 3 + Vite + TypeScript. Chosen over React (team familiarity, Composition API ergonomics) and vanilla JS (maintainability at scale).
2. **State management:** Pinia (Vue 3 native, simpler than Vuex).
3. **Routing:** Vue Router in hash mode (no server-side routing needed for local SPA).
4. **Markdown rendering:** `marked` + `DOMPurify` + `mermaid` (for DIAGRAMMER output).
5. **Backend:** FastAPI + Uvicorn. WebSocket support is first-class. Pydantic v2 models align with existing domain value objects.
6. **API contract:** REST for CRUD (settings, history, learn), WebSocket for debate streaming.
7. **Development proxy:** Vite dev server proxies `/api` and `/ws` to `localhost:8000` — no CORS issues in development.
8. **No authentication in Phase 4.** Local-only. Auth deferred to a future phase.
9. **Frontend location:** `frontend/` directory at repo root (sibling to `backend/`).
   **Consequences:** Clean separation of concerns. The FastAPI server is a thin presentation layer — all business logic stays in `backend/src/`. The Vue SPA can be served as static files by Uvicorn in production (`StaticFiles` mount), eliminating the need for a separate web server.

## ADR 018: 3-Step HITL and Explicit Option Selection

**Date:** 2026-09-19
**Context:** The debate flow originally used a loosely defined Human-In-The-Loop (HITL) pattern where "The Judge" received all architect proposals indiscriminately, and the user provided feedback purely as natural language text. This led to wasted tokens and confusing critiques for options the user already intended to discard.
**Decision:**

1. Break the debate flow into 3 discrete HITL checkpoints: `1_interpreter` (validate problem framing), `2_architects` (select which ideation proposals advance), and `3_judge` (approve the final critiqued selection).
2. Add a `selected_options: list[str]` field to `HITLResponse` so the UI can send an array of explicit solution identifiers (e.g. `["Option Innovator-1"]`) instead of relying on the LLM to parse text feedback.
   **Consequences:** The Judge agent now focuses exclusively on user-selected proposals, greatly reducing token usage and improving the quality of the critique. The UI is required to support checkbox-based selection during the `2_architects` and `3_judge` checkpoints.

## ADR 019: Gemini SDK Migration, Context Caching & Dual Auth

**Date:** 2026-09-19
**Context:** The `google-generativeai` SDK is deprecated in favor of `google-genai`. Furthermore, there is a need to optimize costs for long context windows and allow users to authenticate using their corporate Google Cloud (Vertex AI) quotas rather than personal AI Studio API keys.
**Decision:**

1. **Migration:** Migrate `GeminiAdapter` to the new `google-genai` SDK.
2. **Context Caching:** Implement explicit Context Caching in Gemini for payloads `>= 32,768` tokens (`client.caches.create` and `.delete` per call). For payloads below this limit, use standard generation to avoid the 400 Bad Request API limitation on caching small contexts. OpenAI models naturally fall back to implicit prompt caching.
3. **Dual Authentication:** Update the adapter to prioritize `GOOGLE_CLOUD_PROJECT` for Vertex AI mode (using Application Default Credentials). If absent, use `GEMINI_API_KEY`. If no key is found, fall back to initializing the client without parameters to dynamically pick up ADC generated by the `gemini` CLI for AI Studio (OAuth).
   **Consequences:** Users can seamlessly switch between personal API keys and corporate Vertex AI/OAuth quotas by simply changing environment variables or logging in via the CLI. The application minimizes token processing costs for large RAG contexts automatically.

## ADR 020: Full-Stack Langfuse Observability & Mission-Control UI

**Date:** 2026-10-13
**Context:** The multi-agent debate architecture requires comprehensive telemetry for token usage, latency benchmarks, cost calculation, and prompt debugging. Furthermore, deployment in a self-hosted requires strict resource boundaries to prevent starving the audio stack (Whisper and Kokoro).
**Decision:**

1. **Hexagonal Decoupling:** Introduce `IObservabilityService` port in the Domain layer. `LangfuseObservabilityAdapter` in Infrastructure wraps the Langfuse Python SDK, ensuring the Application and Domain layers remain 100% agnostic to the telemetry provider.
2. **Graceful Degradation:** If the Langfuse server is offline or unreachable, the adapter logs warnings and operates as a no-op, guaranteeing that debates and HITL workflows are never blocked.
3. **Proxy Gateway:** FastAPI acts as the single gateway for the Vue 3 frontend (`/api/observability/*` and WebSocket streaming), preventing exposure of Langfuse credentials in the browser client.
4. **Self-Hosted Docker Resource Caps:** In `docker-compose.yml`, impose strict container resource limits (`ClickHouse: 1GB`, `Langfuse Server: 512MB`, `Postgres: 256MB`, `Redis: 128MB`), reserving >5GB RAM for the host OS and real-time audio models.
5. **Mission-Control UI:** Implement a dedicated Observability view in Vue 3 (cluster gauge, CPU/RAM sparklines, agent latency benchmarks, critical audit highlight, and colored event logs) and enrich `AgentCard.vue` with cumulative token and latency badges.
   **Consequences:** Provides enterprise-grade observability while preserving local-first privacy, system resilience, and adhering to strict clean architecture boundaries.

## ADR 021: Horizontal Scalability Strategy & Hybrid Deployment Profiles (Edge/Homelab vs. Cloud-Native)

**Date:** 2026-11-01
**Context:** The application was initially designed and deployed in a single-node homelab/edge environment utilizing lightweight, zero-configuration local adapters (SQLite, embedded ChromaDB, and local filesystem vault). For academic evaluation (Master's Thesis / TFM) and enterprise readiness, the architecture must formally define and prove horizontal scalability without compromising the low resource footprint required for local homelab execution.
**Decision:**

1. **Hexagonal Scalability Decoupling:** Enforce strict adherence to Clean Architecture ports (`IDebateRepository`, `IAgentConfigRepository`, `IDocumentStore`, `ILLMProvider`, `IObservabilityService`). The domain and application agent logic remains 100% stateless and decoupled from underlying storage engines.
2. **Dual-Deployment Profiles:** Formally define two deployment profiles:
   - *Homelab / Edge Profile (Default):* Uses `SqliteDebateRepository`, embedded `ChromaDBDocumentStore`, and local filesystem markdown vault. Operates under <500 MB RAM baseline with zero cloud cost and single-directory backup ergonomics.
   - *Cloud-Native Distributed Profile (Target Enterprise Scale):* Specifies migration paths to `PostgresDebateRepository` (connection pooling), networked Chroma/Qdrant vector clusters, Redis Pub/Sub for distributed WebSocket event backplanes and HITL session routing, and S3-compatible Object Storage for vault persistence.
3. **Architectural Guard Validation:** Utilize automated architectural tests (`test_decoupling_guard.py`) in CI/CD to prevent leakage of concrete storage, vendor, or agent implementations into generic core modules.
4. **Asynchronous Parallel Streaming:** Leverage `asyncio.gather()` for concurrent specialist deliberation and `AsyncGenerator` streams over WebSockets, ensuring non-blocking event-loop execution regardless of concurrency scale.
   **Consequences:** Validates that the system achieves enterprise-grade horizontal scalability by design while preserving optimal efficiency and zero-cost autonomy for homelab operations. Transitioning between edge and cloud deployments requires only swapping infrastructure adapters without altering core business rules or multi-agent orchestration.

## ADR 022: Authentication, Session Management & Private Debate Isolation

**Date:** 2026-11-09
**Context:** Atenea requires an autonomous authentication system to restrict access to authorized operators and isolate debate histories while keeping the knowledge vault (Obsidian notes) shared across the workspace. In corporate deployments, the design must also allow seamless future integration with Single Sign-On (SSO / OIDC like Keycloak).
**Decision:**
1. **Clean Architecture Domain Port:** Introduce `IUserRepository`, `IPasswordHasher`, and `ITokenService` ports in the Domain layer, with `User` immutable entity.
2. **Minimalist Data Model:** Store strictly necessary credentials (`username`, hashed `password_hash`, `is_admin`, `is_active`, `created_at`). No personal data or bloat.
3. **Argon2id Hashing:** Use `argon2-cffi` (RFC 9106) with memory-hard parameters for robust brute-force resistance.
4. **HttpOnly Session Cookies with Dual Bearer Fallback:** Issue signed HMAC-SHA256 JWT tokens transmitted primarily via `HttpOnly`, `SameSite=Lax`, `Secure` cookies (`atenea_session`), completely eliminating XSS token theft risks and naturally securing HTTP and WebSocket handshakes (`/ws/debate`). Dual support for `Authorization: Bearer <token>` allows CLI and API integrations.
5. **Initial Setup Wizard (Zero-Config First Boot):** If the database has 0 users, the application redirects to `/setup` to initialize the primary administrator account. Once sealed, `/setup` returns 403 Forbidden permanently. User registration is closed (administrators create new operators).
6. **Debate History & Agent Model Configuration Isolation:** The knowledge vault remains 100% shared, but debates are isolated per operator via a `user_id` column in `debates` table. Additionally, agent model configurations (`IAgentConfigRepository`, `UserScopedAgentConfigRepository`) allow each user to independently configure their preferred LLM providers and models per agent (with fallback to system defaults).
7. **Dual Database Adapters:** Provide both `SQLiteUserRepository` for single-node local homelab deployments and `PostgreSQLUserRepository` for enterprise cluster deployments.
8. **Comprehensive API & WebSocket Protection:** All management, upload, audio, debate history, and config endpoints require authenticated user credentials with strict IDOR ownership checks. WebSockets enforce Origin validation and fall-closed handshake authentication. Argon2id operations run in dedicated threads with dummy hash verification to neutralize user-enumeration timing attacks.
9. **Operator Lifecycle & Configurable Deletion Strategy:** Administrators can modify operator roles, activate/suspend accounts, and reset passwords through `PATCH /api/auth/users/{user_id}`. User deletion via `DELETE /api/auth/users/{user_id}` is configurable via `AUTH_DELETE_STRATEGY` (`soft` deactivates the user preserving historical audit trail and debate references; `hard` permanently deletes the record). Critical security invariants strictly forbid self-deactivation, self-demotion, self-deletion, and any operation targeting the last active administrator (`LastAdminError`).
**Consequences:** Provides a rock-solid, production-grade security boundary that runs autonomously with zero external identity dependencies, while remaining forward-compatible with corporate identity federation. Debate histories are private per user without compromising collective architectural intelligence from the shared Obsidian vault.
