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
- **Local Audio Models:** Faster-Whisper (STT) + Kokoro ONNX (TTS) + Vosk (Wake Word)

## 🚀 Getting Started

### 1. Download Local AI Models

Because this system runs voice processing locally to ensure privacy, you must download the necessary AI models before running the backend. We provide a convenient script to do this:

```bash
# Make sure you are in the root directory
chmod +x scripts/download_models.sh
./scripts/download_models.sh
```

*This will download the Kokoro ONNX TTS model and the Vosk Wake Word model into the appropriate `backend/` directories. (Total size ~380MB)*

### 2. Environment Configuration (`.env`)

Copy the template configuration file and configure your API keys:

```bash
cp .env.example .env
```

#### 📊 Observability Toggle (`LANGFUSE_METRICS_ENABLED`)
The full observability stack (Docker containers and backend telemetry) is controlled dynamically via:

```env
# Set to 'true' to launch Docker containers and collect metrics/traces
# Set to 'false' to run in lightweight local mode without Docker
LANGFUSE_METRICS_ENABLED=true
```

- **When `true`:** The backend's FastAPI lifespan automatically orchestrates the Docker stack (`docker compose up -d`) with Postgres, ClickHouse, Redis, MinIO, and Langfuse Web/Worker. The frontend enables the Langfuse Dashboard link.
- **When `false`:** Docker is kept off (or stopped) to save system resources, telemetries are gracefully bypassed with zero overhead, and the UI button is hidden.

### 3. Launching the System

You can run Atenea using either the unified startup script or separate development terminals:

#### 🟢 Option A: Unified Startup Script (Recommended)
Runs Backend, Frontend, and manages Docker in a single command, with clean shutdown on `Ctrl+C`:

```bash
./scripts/start.sh
```

#### 🟡 Option B: Manual Two-Terminal Setup (Development Mode)
If you want independent logs for backend and frontend:

**Terminal 1 — Backend & Docker Orchestration:**
```bash
cd backend
source .venv/bin/activate
uvicorn src.presentation.api.app:app --reload
```

**Terminal 2 — Frontend (Vue 3 / Vite):**
```bash
cd frontend
npm run dev
```

### 4. Available Services & Endpoints

Once started, the following services will be available:

| Service | URL | Condition |
| :--- | :--- | :--- |
| **Frontend UI (Atenea)** | [http://localhost:5173](http://localhost:5173) | Always Active |
| **Backend API & Swagger Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | Always Active |
| **Langfuse Telemetry Dashboard** | [http://localhost:3000](http://localhost:3000) | Active when `LANGFUSE_METRICS_ENABLED=true` |
| **MinIO Console (S3 Storage)** | [http://localhost:9091](http://localhost:9091) | Active when `LANGFUSE_METRICS_ENABLED=true` |

