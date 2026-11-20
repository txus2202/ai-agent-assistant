---
created: 2026-10-13
updated: 2026-10-13
type: spec
phase: 6
layer: infrastructure
status: implemented
tags: [observability, langfuse, telemetry, metrics, vue3, clean-architecture]
category: meta-project
---

# Feature Specification: Full-Stack Observability with Langfuse & Mission-Control UI

## 1. Overview & Business Value

This specification defines the observability architecture for **ATENEA** (Asistente Técnica y Evaluadora de Nuevas Estructuras y Arquitecturas), providing end-to-end tracing, performance metrics, token accounting, and live system telemetry across the entire multi-agent supervisor ecosystem.

Observability is divided into two operational tiers:
1. **System & Supervisor Level (ATENEA Global):** Debate duration, total token usage, economic cost estimation ($ USD), execution waterfall, hardware health (CPU/RAM load for Intel N100 homelab), and HITL checkpoint tracking.
2. **Specialist Agent Level:** Per-agent latency benchmarks, prompt transparency, RAG context inspection (documents retrieved from Obsidian/ChromaDB), model hyperparameters, and token usage breakdown displayed on agent cards.

The frontend incorporates a dedicated **Mission-Control Observability Tab** based on the cyberpunk/retro-futuristic UI design specification.

---

## 2. Architecture & Clean Architecture Compliance

Adhering strictly to Clean Architecture (ADR-004), the core Domain and Application layers must remain completely decoupled from the third-party `langfuse` SDK.

```
┌────────────────────────────────────────────────────────┐
│                   Presentation Layer                   │
│   - FastAPI Routes: /api/observability/*               │
│   - WebSocket Event Stream (real-time telemetry)       │
│   - Vue 3: ObservabilityPanel.vue, AgentCard metrics   │
└──────────────────────────┬─────────────────────────────┘
                           │ calls
┌──────────────────────────▼─────────────────────────────┐
│                   Application Layer                    │
│   - SupervisorAgent (instruments debate lifecycle)     │
│   - SubAgentRunner (instruments agent generation spans)│
│   - QueryObservabilityUseCase                          │
└──────────────────────────┬─────────────────────────────┘
                           │ depends on Port (Protocol)
┌──────────────────────────▼─────────────────────────────┐
│                     Domain Layer                       │
│   - IObservabilityService (Abstract Protocol)          │
│   - Value Objects: TraceContext, AgentSpanMetrics      │
└──────────────────────────▲─────────────────────────────┘
                           │ implements
┌──────────────────────────┴─────────────────────────────┐
│                  Infrastructure Layer                  │
│   - LangfuseObservabilityAdapter (Langfuse Python SDK) │
│   - SystemMetricsCollector (psutil for CPU/RAM load)   │
│   - Docker Compose: Langfuse Stack with memory caps    │
└────────────────────────────────────────────────────────┘
```

### 2.1 Domain Layer (`src/domain/ports/observability.py`)
- Defines `IObservabilityService` interface (Protocol):
  - `start_trace(name: str, session_id: str, metadata: dict) -> TraceContext`
  - `end_trace(trace_context: TraceContext, status: str, output: any = None)`
  - `start_agent_span(trace_context: TraceContext, agent_role: str, input_prompt: str, metadata: dict) -> SpanContext`
  - `end_agent_span(span_context: SpanContext, output: str, token_counts: dict | None, latency: float)`
  - `record_system_metrics() -> dict` (CPU load, memory load)

### 2.2 Infrastructure Layer (`src/infrastructure/observability/`)
- `LangfuseObservabilityAdapter`: Implements `IObservabilityService` using `langfuse.Langfuse` client.
  - Safe degradation: If Langfuse container is unreachable or unconfigured, it logs a warning and degrades gracefully (noop) without blocking debate execution.
- `SystemMetricsCollector`: Reads current host/container CPU and RAM usage via `psutil`.

### 2.3 Presentation Layer
- **Backend API (`src/presentation/api/routes/observability.py`):**
  - `GET /api/observability/stats`: Global cluster health, current active agent, system load.
  - `GET /api/observability/sessions/{session_id}`: Detailed trace summary with per-agent latency breakdown and token metrics.
- **Frontend (Vue 3 / TypeScript):**
  - Toggle in `ChatPanel.vue` between `[OBSERVABILIDAD]` and `[CHAT CON IA]`.
  - `ObservabilityPanel.vue`:
    1. Radial cluster gauge (`99.8% CLUSTER`, `AUDIT ONLINE`).
    2. CPU and Memory sparkline charts (dual-thread / quad-core N100 tracking).
    3. Agent Latency Benchmarks bar chart with real-time running timers and states.
    4. Active Stage / Critical Audit highlight card (`Devil's Advocate / The Judge`).
    5. Terminal Event Stream with colorized log tags (`[SYSTEM]`, `[PIPELINE]`, `[THE JUDGE]`).
  - `AgentCard.vue`:
    - Displays cumulative tokens consumed (e.g., `1.2k tkns`) and average latency (e.g., `0.48s`).

---

## 3. Homelab Docker Deployment & Resource Limits

To preserve privacy and prevent starvation of voice models (`faster-whisper`, `kokoro-onnx`) on the target Intel N100 (12GB DDR5 RAM, 512GB SSD), Langfuse runs self-hosted with strict resource boundaries:

```yaml
version: "3.8"
services:
  clickhouse:
    image: clickhouse/clickhouse-server:latest
    deploy:
      resources:
        limits:
          memory: 1024M
          cpus: "1.0"
  langfuse-server:
    image: langfuse/langfuse:latest
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: "1.0"
  postgres:
    image: postgres:16-alpine
    deploy:
      resources:
        limits:
          memory: 256M
  redis:
    image: redis:7-alpine
    deploy:
      resources:
        limits:
          memory: 128M
```

---

## 4. Acceptance Criteria & Test Plan (TDD)

### 4.1 Backend Acceptance Criteria
1. **GIVEN** a debate started by `SupervisorAgent`, **WHEN** execution begins, **THEN** an active trace is created with the session ID.
2. **GIVEN** each sub-agent invocation (`SubAgentRunner`), **WHEN** the agent processes a prompt, **THEN** a generation span is recorded capturing the input prompt, RAG context, tokens, and duration.
3. **GIVEN** Langfuse is offline or unreachable, **WHEN** an agent runs, **THEN** the debate completes normally without raising unhandled infrastructure exceptions.
4. **GIVEN** `GET /api/observability/stats`, **WHEN** queried, **THEN** it returns CPU load, memory usage, and current agent states with HTTP 200.

### 4.2 Frontend Acceptance Criteria
1. **GIVEN** `ChatPanel.vue`, **WHEN** clicking the `[OBSERVABILIDAD]` tab, **THEN** the view switches to `ObservabilityPanel` while retaining chat state.
2. **GIVEN** `ObservabilityPanel.vue`, **WHEN** mounted, **THEN** it renders the cluster health gauge, CPU/RAM sparklines, agent latency progress bars, and event stream.
3. **GIVEN** `AgentCard.vue`, **WHEN** updated during a debate, **THEN** it displays updated token counts and response latency badges.
