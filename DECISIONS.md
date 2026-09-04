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
