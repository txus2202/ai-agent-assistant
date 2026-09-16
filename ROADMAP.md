# Project Roadmap

| Phase       | Focus                        | Key Deliverables                                                                                                     | Status      |
| :---------- | :--------------------------- | :------------------------------------------------------------------------------------------------------------------- | :---------- |
| **Phase 1** | **Foundation & Core Engine** | Domain entities (Agent, Task), domain ports (ILLMProvider, IAgentRepository, ITaskRepository), RunAgentTask use case, InMemoryAgentRepository + InMemoryTaskRepository, domain exceptions, 52 tests passing. | [x] Done — 2026-09-08 |
| **Phase 2** | **Obsidian Brain (RAG) & Persistence** | SQLiteAgentRepository + SQLiteTaskRepository (ADR-011), IDocumentStore port + DocumentChunk/SearchFilter value objects, ChromaDBDocumentStore (sentence-transformers local, ADR-012), ObsidianParser (H2/H3 section chunks + YAML frontmatter as metadata), IngestVault service + CLI script (`scripts/ingest_vault.py`), InMemoryDocumentStore (test double). 85 tests passing. | [x] Done — 2026-09-15 |
| **Phase 3** | **AI Team, Learning Agent & Multi-Provider** | **Specs (5):** LLM Adapters (Gemini/OpenAI/Anthropic + LLMProviderRegistry, ADR-013), QueryVault use case, Learning Agent — PDF+URL→structured .md→ChromaDB (ADR-014), Sub-Agent Definitions (AgentRole, SubAgentProfile, SubAgentRunner), Supervisor Agent + HITL event stream (ADR-015). **ADK deferred to Phase 4.** | [ ] In Progress — specs done 2026-09-15 |
| **Phase 4** | **Interactive UI & ADK**     | Vue 3 SPA, FastAPI WebSocket streaming, Google ADK adapter wrapping Supervisor, Settings screen (API key validation + dynamic model dropdowns), optional API-based embedding upgrade (e.g., `text-embedding-004`). | [ ] Pending |
| **Phase 5** | **Voice Integration**        | Local Whisper.cpp (STT) and Piper (TTS) integration for hands-free interactions.                                     | [ ] Pending |

---

## Agent Team Backlog (deferred, post Phase 3)

> Items to address once the Supervisor + HITL loop is functional end-to-end.

| # | Item | Notes |
|---|---|---|
| 1 | **Prompt tuning & iteration** | Each agent's `system_prompt` will need real-world testing and refinement once connected to a live LLM. Quality of debate output depends heavily on prompt precision. |
| 2 | **Greek mythology naming** | Rename agents using Greek mythology personas (e.g. Athena → strategist, Prometheus → innovator, Themis → judge, Hephaestus → builder/DevOps, Hermes → interpreter, Daedalus → architect/diagrammer). Names should reflect each agent's role and personality. A dedicated ADR will be created when naming is finalised, as it affects `AgentRole` enum values and `display_name` fields. |
| 3 | **New sub-agents** | Candidates: Security Auditor (focused on OWASP / threat modelling), Documentation Agent (auto-generates MkDocs content from debate outputs), Code Reviewer (reviews PRs against ADRs and specs). Each new agent requires a spec, TDD cycle, and a `SubAgentProfile`. |
| 4 | **Agent memory / context window management** | Long debates will exceed context limits. Strategy needed: summarisation, sliding window, or per-agent conversation history. |
| 5 | **Agent personalities & tone calibration** | Beyond role instructions, agents should have a consistent personality (e.g. The Judge is dry and unsparing; the Innovator is enthusiastic). Personality guidelines to be defined per agent. |
