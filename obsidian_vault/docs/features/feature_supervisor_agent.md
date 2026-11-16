---
created: 2026-09-15
updated: 2026-09-15
type: spec
phase: 3
layer: application
status: implemented
tags: [supervisor, hitl, orchestration, multi-agent, events, application, atenea]
---

# Feature: Supervisor Agent & Human-In-The-Loop

**As a** user
**I want** to submit an architectural request to ATENEA and receive a structured debate between specialized agents
**So that** I get multiple expert perspectives, can review intermediate proposals, and approve the final consolidated response.

## Context & Motivation

The Supervisor implements the pattern described in `PROJECT_CONTEXT.md`. It orchestrates the 6 sub-agents in a defined sequence, yielding typed events at each step. HITL checkpoints allow the user to steer the debate before it continues.

Google ADK is deferred to Phase 4 (ADR-015). Phase 3 uses Clean Architecture pura.

## Event Model

The Supervisor yields a stream of typed events. This makes it compatible with WebSocket streaming (Phase 4, ADR-003) and testable without a running server.

```python
class EventType(Enum):
    AGENT_STARTED    = "agent_started"
    AGENT_COMPLETED  = "agent_completed"
    HITL_REQUIRED    = "hitl_required"
    DONE             = "done"

@dataclass(frozen=True)
class SupervisorEvent:
    type: EventType
    role: AgentRole | None       # None for DONE
    content: str                 # agent output or HITL prompt or final summary
    metadata: dict[str, str]
```

## Debate Flow

```
User request
    1. NL_INTERPRETER  → formalized_request       [AGENT_STARTED → AGENT_COMPLETED]
    2. INNOVATOR        → proposal_a              [AGENT_STARTED → AGENT_COMPLETED]
    3. SENIOR_ARCHITECT → proposal_b              [AGENT_STARTED → AGENT_COMPLETED]
    4. THE_JUDGE        → critique                [AGENT_STARTED → AGENT_COMPLETED]
    5. ──── HITL checkpoint ① ────                [HITL_REQUIRED]
       User: "approve" | "reject" | "refine: ..."
    6. DIAGRAMMER       → mermaid diagram         [AGENT_STARTED → AGENT_COMPLETED]
    7. DEVOPS_SECOPS    → deployment notes        [AGENT_STARTED → AGENT_COMPLETED]
    8. ──── HITL checkpoint ② ────                [HITL_REQUIRED]
       User: "approve" | feedback
    9. Final consolidation                        [DONE]
```

## Service Contract

```python
class HITLDecision(Enum):
    APPROVE = "approve"
    REJECT  = "reject"
    REFINE  = "refine"    # user provides additional instructions

@dataclass
class HITLResponse:
    decision: HITLDecision
    feedback: str = ""    # required when decision == REFINE

SupervisorAgent.run(
    user_request: str,
    llm_provider: ILLMProvider,
    document_store: IDocumentStore,
    model_name: str,
    hitl_callback: Callable[[SupervisorEvent], HITLResponse],
) -> Generator[SupervisorEvent, None, None]
```

`hitl_callback` is called synchronously when a `HITL_REQUIRED` event is yielded.
In Phase 4 (FastAPI/WebSocket), this callback will be an async coroutine.

## Acceptance Criteria

### Scenario 1: Full flow yields events in correct order

```
Given a SupervisorAgent with mocked sub-agents and HITL callback always returning APPROVE
When SupervisorAgent.run(user_request="Propose a caching strategy") is called
Then events are yielded in order:
  AGENT_STARTED(NL_INTERPRETER)
  AGENT_COMPLETED(NL_INTERPRETER)
  AGENT_STARTED(INNOVATOR)
  AGENT_COMPLETED(INNOVATOR)
  ...
  HITL_REQUIRED
  ...
  DONE
```

### Scenario 2: HITL_REQUIRED event carries the proposals and critique

```
Given agents have completed and HITL checkpoint ① is reached
When the HITL_REQUIRED event is yielded
Then event.content contains summaries of INNOVATOR, SENIOR_ARCHITECT, and THE_JUDGE responses
```

### Scenario 3: REJECT at HITL ① re-runs INNOVATOR and SENIOR_ARCHITECT

```
Given HITL callback returns HITLResponse(decision=REJECT) at checkpoint ①
When SupervisorAgent continues
Then INNOVATOR and SENIOR_ARCHITECT are invoked a second time
And a new HITL_REQUIRED is yielded after the re-run
```

### Scenario 4: REFINE at HITL ① appends user feedback to subsequent agent prompts

```
Given HITL callback returns HITLResponse(decision=REFINE, feedback="focus on latency")
When DIAGRAMMER is invoked after the checkpoint
Then its prompt includes "focus on latency"
```

### Scenario 5: DONE event carries the consolidated final response

```
Given all agents complete and HITL ② returns APPROVE
When the DONE event is yielded
Then event.content contains the full consolidated markdown response
```

### Scenario 6: SupervisorAgent emits at least 12 events for a full approve flow

```
Given HITL always returns APPROVE
When SupervisorAgent.run() is exhausted
Then len(list(events)) >= 12  (2 per agent × 6 agents + 2 HITL + 1 DONE)
```

## Implementation Notes

- `SupervisorEvent`, `EventType`, `HITLDecision`, `HITLResponse` → `src/domain/agents/supervisor_events.py`
- `SupervisorAgent` → `src/application/agents/supervisor_agent.py` (consistent with SubAgentRunner)
- Tests use `SubAgentRunner.run` mocked at the module level via `monkeypatch`
- The `hitl_callback` in tests returns `HITLResponse(decision=APPROVE)` by default
- Phase 4 will replace the synchronous callback with an `asyncio.Queue` or WebSocket send/receive
- Consolidation in the `DONE` event is done by a final LLM call with all agent outputs as context

### REJECT vs REFINE semantics

| Decision | At HITL ① | At HITL ② |
|---|---|---|
| `APPROVE` | Continue to DIAGRAMMER + DEVOPS | Continue to consolidation |
| `REJECT` | Re-run INNOVATOR + SENIOR + JUDGE (unlimited retries) | Re-run DIAGRAMMER + DEVOPS (unlimited retries) |
| `REFINE` | Carry feedback forward to DIAGRAMMER + DEVOPS (no re-run of architects) | Carry feedback forward to consolidation |

No retry cap — the debate continues until the user is satisfied.
Timeout management is deferred to the presentation layer (WebSocket/Phase 4).
