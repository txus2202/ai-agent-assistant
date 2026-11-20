---
created: 2026-09-17
updated: 2026-09-17
type: spec
phase: 4
layer: presentation
status: draft
tags: [chat, observability, agent-cards, hitl, vue, left-panel, right-panel, atenea]
category: meta-project
---

# Feature: Chat UI, Agent Topology & HITL Panel

**As a** user
**I want** to write an architectural query, monitor each agent's progress in real time, and approve or steer the debate at HITL checkpoints
**So that** I stay in control of the multi-agent debate without losing visual context.

> This spec supersedes the earlier `feature_chat_ui.md` skeleton.
> Design is based on the Stitch prototype (4 screens analyzed).

## Left Panel — Two Tabs

### Tab 1: OBSERVABILIDAD

Shows system telemetry. Always visible regardless of debate state.

```
┌─ SYSTEM OBSERVABILITY ─────── ● HEALTHY ─┐
│  [Donut: 100% STANDBY / 0/6 agents]       │
│  CPU LOAD  ████░░░░  12%                  │
│  MEMORY    █████░░░  42%                  │
├─ AGENT LATENCY BENCHMARKS ───────────────┤
│  ● Natural Interpreter    Standby (0.0s) │
│  ● Senior Architect       Standby (0.0s) │
│  ● Innovator Architect    Standby (0.0s) │
│  ● The Judge              Standby (0.0s) │
├─ PIPELINE STATUS ────────────────────────┤
│  Thread A (Senior Arch): 0.00% INACTIVE  │
│  Thread B (Innovator):   0.00% INACTIVE  │
│  ℹ STANDBY MODE: Awaiting query.         │
├─ LOGS / EVENT STREAM ─── ● DUAL_STREAM ─┤
│  [SYSTEM] A.T.E.N.E.A. initialized...    │
│  [SUPERVISOR] All 6 nodes registered...  │
│  [AWAITING] Ingrese consulta...           │
│  ...scrolling log...                      │
└───────────────────────────────────────────┘
```

**Donut chart** color = same as active agent color (white on idle).
**Log entries** colored by source: `[SYSTEM]`=slate, `[SUPERVISOR]`=cyan, `[THE JUDGE]`=rose, `[INNOVATOR]`=lime, `[SENIOR ARCH]`=emerald.

### Tab 2: CHAT CON IA (active tab during debate)

```
┌─ CONVERSACIÓN ARQUITECTÓNICA ──────────┐
│  [Limpiar] [Exportar]                   │
│  ✓ 4 archivos de contexto cargados  v3 │
│  ARQUITECTO LÍDER (TÚ) 👤              │
│  ┌──────────────────────────────────┐  │
│  │ ¿Cómo desacoplamos el módulo     │  │
│  │ de facturación para resistir     │  │
│  │ 50.000 ops/s?                    │  │
│  └──────────────────────────────────┘  │
│                                         │
│  A.T.E.N.E.A. [SUPERVISOR AGENT]       │
│  ┌──────────────────────────────────┐  │
│  │ Analizando topología...           │  │
│  │ Senior Architect propone patrón  │  │
│  │ Event-Driven con Kafka...         │  │
│  │ ┌──────────────────────────────┐ │  │
│  │ │ COMPARATIVA RECOMENDADA      │ │  │
│  │ │ 1. Kafka+Outbox 2. CQRS+Rep  │ │  │
│  │ └──────────────────────────────┘ │  │
│  └──────────────────────────────────┘  │
│                                         │
│  [+ Evaluar resilencia][+ Diseñar C4]  │  ← quick-action chips
│  [+ Políticas Zero-Trust]              │
│  ┌────────────────────────────────┐    │
│  │ Escribe tu consulta...      ➤  │    │
│  └────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

**Chat rendering rules:**
- User messages: right-aligned, dark teal bubble (`bg-space-750 border border-cyan-800/40`)
- Agent (supervisor) messages: left-aligned, darker bubble with ATENEA badge
- Markdown rendered via `marked` + `DOMPurify`
- Mermaid diagrams rendered inline via `mermaid` JS
- Structured comparison tables rendered as side-by-side cards
- "Limpiar" clears current chat (prompts confirmation)
- "Exportar" downloads debate as Markdown file
- Quick-action chips: context-aware suggestions updated as debate progresses

**Input:**
- Multiline textarea, `Enter` = newline, `Ctrl+Enter` or click ➤ = send
- Disabled while `status === 'hitl_waiting'` or `status === 'running'` (agent is working)

## Right Panel — Agent Topology

```
┌─ AGENT TOPOLOGY (LANGGRAPH) ── ● 2 AGENTS CONCURRENT ─┐
│                                                          │
│  [💬] NATURAL LANGUAGE INTERPRETER          ●● (idle)  │
│       ● STATUS: IDLE / COMPLETED (#00b4d8)              │
│       MODEL: GEMINI PRO / GPT-4O         LATENCY: 480ms │
│                                                          │
│  [⚙] SENIOR ARCHITECT        [ACTIVE CO-EXEC]  ●● ─── │
│  ┌───────────────────────────────────────────────────┐  │
│  │ ● STATUS: PROCESSING (CORE PATTERNS & CQRS)       │  │
│  │ SPEC & PATTERNS: EVENT-DRIVEN / CQRS / DDD        │  │
│  │ FLUX SECTOR: 16.67% (VERDE OSCURO)    1.4s ───    │  │
│  │ ████░░░░░░░░░░░░░░░░░░                            │  │
│  └───────────────────────────────────────────────────┘  │
│                                                          │
│  [⚠] THE JUDGE (DEVIL'S ADVOCATE)      IDLE #ef4444    │
│       ● STANDBY: QUEUED FOR CROSS-VALIDATION            │
│       SCALABILITY BENCHMARK          WAITING DUAL OUTPUT │
│                                                          │
│  ... (Diagrammer, DevOps, Innovator)                     │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐│
│  │ 🔗 CONCURRENT CO-SYNTHESIS ACTIVE                   ││
│  │ Parallel consensus running between Senior Architect  ││
│  │ and Innovator Architect...                           ││
│  │                                                      ││
│  │   [🔀 MERGE PARALLEL SYNTHESIS OUTPUTS]             ││  ← HITL button
│  └─────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────┘
```

### Agent Card states

| State | Badge text | Border/Glow | Dots |
|---|---|---|---|
| STANDBY | `STANDBY` | `border-slate-700` | `●● gray` |
| ACTIVE | `ACTIVE CO-EXEC` | `border-emerald-500 glow-green` | `●● agent-color` |
| COMPLETED | `COMPLETED` | `border-slate-600` | `●● faded` |
| WAITING | `IDLE #hex` | `border-slate-700` | `●● gray` |

Active cards show a progress bar that fills over time (indeterminate, color = agent color).

### Orchestration Card (bottom of right panel)

Changes content and button based on debate phase:

| Phase | Card title | Button text | Button color |
|---|---|---|---|
| Idle | `ORQUESTACIÓN EN ESPERA` | `SIMULATE QUERY TO ACTIVATE` | cyan |
| HITL ① | `CONCURRENT CO-SYNTHESIS ACTIVE` | `MERGE PARALLEL SYNTHESIS OUTPUTS` | emerald |
| Judge audit | `JUDGE AUDIT VALIDATION` | `APPROVE JUDGE CRITIQUE / PROCEED` | rose |
| HITL ② | `IMPLEMENTATION REVIEW` | `APPROVE & CONSOLIDATE` | emerald |
| Done | `DEBATE COMPLETE` | `VIEW SUMMARY` | cyan |

### HITL Decision flow (right panel)

When `HITL_REQUIRED` event arrives:
1. Orchestration card updates with debate summary text
2. Primary button changes to context text (e.g. "MERGE PARALLEL SYNTHESIS OUTPUTS")
3. Clicking the button = `APPROVE`
4. A secondary "REFINE" link appears below: clicking it opens a small textarea overlay for feedback
5. A tertiary "RE-RUN" link appears for `REJECT`
6. After decision is sent, debate continues and cards update

> No blocking modal. HITL is integrated natively into the right panel flow.

## Center — Particle Orb & Status

The orb reacts to the debate state (see `feature_ui_shell.md`).

Below the orb: a status bar showing:
- Active flux % (e.g. `CO-EXECUTION ACTIVE: 33.33% FLUX`)
- Breakdown per active agent with color codes
- Below that: orb topology stats

## Bottom — VoiceBar

```
[ 🎤 MIC VOZ  LISTO PARA ESCUCHAR ]   [— SILENCIO]   [● IA (VERDE)]   [● USUARIO (AZUL)]
```

- MIC button: opens voice input (Phase 5). Disabled in Phase 4 with tooltip "Voice available in Phase 5."
- SILENCIO toggle: mute system audio
- IA / USUARIO dots: connection indicators for WebSocket state

## Pinia Store — `useDebateStore`

```typescript
interface DebateStore {
  status: 'idle' | 'connecting' | 'running' | 'hitl_waiting' | 'done' | 'error'
  activeRole: AgentRole | null          // currently running agent
  events: SupervisorEvent[]             // all events received
  chatMessages: ChatMessage[]           // rendered chat history
  hitlEvent: SupervisorEvent | null     // current HITL event waiting
  error: string | null

  // actions
  startDebate(request: DebateRequest): void
  sendHITL(decision: HITLDecision, feedback?: string): void
  clearChat(): void
  exportDebate(): void
}
```

## Acceptance Criteria

### Scenario 1: Left tab switches between Observability and Chat

```
Given the interface is loaded
When user clicks "CHAT CON IA" tab
Then Chat panel becomes visible with input focused
When user clicks "OBSERVABILIDAD" tab
Then system health metrics are shown
```

### Scenario 2: Agent card glows when AGENT_STARTED received

```
Given debate is running
When AGENT_STARTED event for THE_JUDGE is received
Then AgentCard for THE_JUDGE adds glow-red class and shows active badge
And orb beam color transitions to red
```

### Scenario 3: HITL button enables when hitl_waiting

```
Given status === 'running'
Then HITL button is disabled (loading state)
When HITL_REQUIRED event received
Then status = 'hitl_waiting'
And orchestration card updates with summary
And HITL button becomes clickable
```

### Scenario 4: Refine flow opens feedback textarea

```
Given HITL checkpoint ① is active
When user clicks "REFINE" link
Then a textarea appears below the orchestration card
And a "SEND REFINEMENT" button is shown
When user types feedback and sends
Then HITLResponse(REFINE, feedback) is sent over WebSocket
```

### Scenario 5: Chat exports to markdown

```
Given debate has completed
When user clicks "Exportar"
Then browser downloads debate.md file
And file contains all agent responses in structured Markdown
```

## Implementation Notes

- `useDebateSocket` composable handles WebSocket + HITL channel (see `feature_websocket_debate.md`)
- Left panel tabs: Vue's `v-show` (not `v-if`) to preserve scroll position on tab switch
- `EventLog.vue` uses a virtual scroll or `max-h` + `overflow-y: auto` with auto-scroll
- Agent card progress bars: CSS `@keyframes` width animation, reset on each new agent turn
- Mermaid rendering: `mermaid.run()` called after DOM update via `nextTick`
- Quick-action chips: derived from debate phase in `useDebateStore` getter
