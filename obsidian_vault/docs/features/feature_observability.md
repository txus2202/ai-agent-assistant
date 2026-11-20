---
created: 2026-10-13
updated: 2026-11-20
type: spec
phase: 6
layer: infrastructure
status: implemented
tags: [observability, langfuse, telemetry, metrics, vue3, clean-architecture, context-cache]
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

### 2.4 Session Context Cache & Cached Token Accounting (`cached_tokens`)
To accurately populate the `SESSION CONTEXT CACHE` telemetry widget in `ObservabilityPanel.vue` (`sessionCachedTokens` and `cacheSavingsPercentage`) without synthetic client-side fabrication:
1. **LLM Provider Native Cache Extraction (`usage_tracking.py` & Adapters):**
   - `build_usage(input_tokens, output_tokens, total_tokens=None, cached_tokens=0)` normalizes integer token counters and includes `"cached": cached_t` when `cached_t > 0`.
   - `GeminiAdapter`: extracts `usage_metadata.cached_content_token_count` in `complete_with_usage()` and `complete_stream()`.
   - `OpenAIAdapter`: extracts `usage.prompt_tokens_details.cached_tokens` in `complete_with_usage()`.
   - `AnthropicAdapter`: extracts `usage.cache_read_input_tokens` in `complete_with_usage()` and `complete_stream()`.
2. **Session Context Reuse Accounting (`SubAgentRunner`, `SupervisorAgent`, `consolidation_service.py`):**
   - When an LLM provider does not report explicit SDK cache hits (`cached == 0`), `SubAgentRunner._calculate_usage()` accounts for the reused session context injected into the prompt (RAG `context_block`, `chat_history` from prior turns, and accumulated multi-agent debate context headers `## Formalized Requirements`, `## Architectural Proposals`, `## Peer Review Critiques`, `## Critical Evaluation`, `--- Aportaciones del Consejo ---`), capped at `input` tokens (`min(in_tkn, reusable_context_chars // 4)`).
   - `SupervisorAgent` (`_run_direct_chat_mode`, `_build_role_runner`) and `run_consolidation` emit `"cached_tokens": str(cached_tokens)` in `AGENT_COMPLETED` and `DONE` event `metadata`.

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
5. **GIVEN** an LLM adapter response with provider-level cached tokens (`cached_content_token_count`, `prompt_tokens_details.cached_tokens`, or `cache_read_input_tokens`), **WHEN** `complete_with_usage()` or `complete_stream()` finishes, **THEN** `get_last_usage()` includes `"cached"` with the exact count.
6. **GIVEN** a multi-agent debate or multi-turn session with RAG context, chat history, or shared council outputs, **WHEN** `SubAgentRunner` or `SupervisorAgent` emits `AGENT_COMPLETED` / `DONE`, **THEN** `event.metadata["cached_tokens"]` reports the native or reused session context tokens (`> 0`).

### 4.2 Frontend Acceptance Criteria
1. **GIVEN** `ChatPanel.vue`, **WHEN** clicking the `[OBSERVABILIDAD]` tab, **THEN** the view switches to `ObservabilityPanel` while retaining chat state.
2. **GIVEN** `ObservabilityPanel.vue`, **WHEN** mounted, **THEN** it renders the cluster health gauge, CPU/RAM sparklines, agent latency progress bars, and event stream.
3. **GIVEN** `AgentCard.vue`, **WHEN** updated during a debate, **THEN** it displays updated token counts and response latency badges.
