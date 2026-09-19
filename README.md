# 🤖 AI Agent Assistant

**AI Agent Assistant** is an advanced Artificial Intelligence agent system designed to assist in the design, evaluation, and documentation of software architectures. Developed as a Master's Thesis, this project stands out for its strict focus on **enterprise data privacy** and the implementation of **Clean Architecture**.

The system acts as a team of experts orchestrated under the **Supervisor Pattern**, interacting seamlessly with a local knowledge base (Obsidian) and keeping the core code and business logic completely decoupled from the underlying AI framework.

## ✨ Key Features

- 🔒 **Total Privacy (Local-First):** LLM integration via secure APIs (Gemini Enterprise) and 100% local execution for both the vector database (ChromaDB) and voice models. No sensitive corporate data ever leaks to public clouds.
- 🧠 **Multimodal RAG with Obsidian:** Capable of reading, vectorizing, and understanding both Markdown text files (`.md`) and locally stored architectural diagrams. The system continuously learns by saving its finalized solutions back into the _Vault_.
- 🗣️ **Voice Interaction (STT/TTS):** Hands-free system control via voice commands processed locally using `Whisper.cpp`, with responses naturally synthesized by `Piper`.
- 🏗️ **Clean Architecture & TDD:** Highly testable modular monolithic design. The application's core domain does not depend on any external AI frameworks (like Google ADK) or infrastructure libraries.
- ⚡ **Real-Time Streaming:** A FastAPI backend communicating via WebSockets with a Vue 3 SPA to stream the agent's reasoning process and output tokens live.

## 🛠️ Tech Stack

- **Frontend:** Vue 3 + TypeScript
- **Backend:** Python (FastAPI)
- **AI Orchestration:** Google ADK (Agent Development Kit)
- **Vector DB & Observability:** ChromaDB + Langfuse (Docker)
- **Local Audio Models:** Whisper.cpp (STT) + Piper (TTS)
