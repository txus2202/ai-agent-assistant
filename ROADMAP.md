# Project Roadmap

| Phase       | Focus                        | Key Deliverables                                                                                                     | Status      |
| :---------- | :--------------------------- | :------------------------------------------------------------------------------------------------------------------- | :---------- |
| **Phase 1** | **Foundation & Core Engine** | Domain entities (Agent, Task), domain ports (ILLMProvider, IAgentRepository), RunAgentTask use case, InMemoryAgentRepository, domain exceptions, 33 tests passing. | [x] Done — 2026-09-06 |
| **Phase 2** | **The Obsidian Brain (RAG) & Persistence** | Local ingestion script, ChromaDB integration, Frontmatter/MOC indexing logic, and `SQLiteAgentRepository` + `SQLiteTaskRepository` as the default persistent adapters (ADR-011). | [ ] Pending |
| **Phase 3** | **AI Team & Multi-Provider** | Sub-agents implementation, Human-In-The-Loop flow, and LLM Adapters with dynamic model fetching via API keys.        | [ ] Pending |
| **Phase 4** | **Interactive UI**           | Vue 3 SPA initialization, Settings screen (API key validation and dynamic model dropdowns), and WebSocket streaming. | [ ] Pending |
| **Phase 5** | **Voice Integration**        | Local Whisper.cpp (STT) and Piper (TTS) integration for hands-free interactions.                                     | [ ] Pending |
