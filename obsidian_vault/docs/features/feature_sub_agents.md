---
created: 2026-09-15
updated: 2026-09-15
type: spec
phase: 3
layer: domain
status: draft
tags: [agents, roles, sub-agents, system-prompt, rag, domain]
---

# Feature: Sub-Agent Definitions & Runner

**As a** Supervisor Agent
**I want** to invoke specialized sub-agents by role
**So that** each agent applies its specific expertise and can optionally ground its response with RAG-retrieved context.

## Context & Motivation

Per `PROJECT_CONTEXT.md`, ATENEA has 6 specialized roles. This spec formalises them as:
- A `AgentRole` enum (Domain)
- A `SubAgentProfile` value object holding each agent's configuration
- A `SubAgentRunner` application service that executes a single agent with RAG + LLM

## AgentRole Enum (Domain)

```python
class AgentRole(Enum):
    NL_INTERPRETER   = "nl_interpreter"
    INNOVATOR        = "innovator_architect"
    SENIOR_ARCHITECT = "senior_architect"
    THE_JUDGE        = "the_judge"
    DEVOPS_SECOPS    = "devops_secops"
    DIAGRAMMER       = "diagrammer"
```

## SubAgentProfile (Domain Value Object)

```python
@dataclass(frozen=True)
class SubAgentProfile:
    role: AgentRole
    display_name: str
    system_prompt: str
    uses_rag: bool
    rag_filter: SearchFilter | None   # None = no filter (all vault)
```

All 6 profiles defined in `src/domain/agents/sub_agent_profiles.py` as module-level constants.

## SubAgentRunner (Application Service)

```python
@dataclass
class SubAgentResponse:
    role: AgentRole
    content: str               # LLM response text
    context_chunks: list[DocumentChunk]  # RAG chunks used (empty if uses_rag=False)

SubAgentRunner.run(
    role: AgentRole,
    user_request: str,
    llm_provider: ILLMProvider,
    document_store: IDocumentStore,
    model_name: str,
) -> SubAgentResponse
```

Pipeline:
1. Load `SubAgentProfile` for `role`
2. If `uses_rag`: `QueryVault.run(user_request, filter=profile.rag_filter)`
3. Build prompt: `system_prompt + context_block + user_request`
4. Call `llm_provider.complete(prompt, model_name)`
5. Return `SubAgentResponse`

## Sub-Agent Profiles

| Role | display_name | uses_rag | rag_filter |
|---|---|---|---|
| `NL_INTERPRETER` | Natural Language Interpreter | No | — |
| `INNOVATOR` | Innovator Architect | Yes | `SearchFilter(type="spec")` |
| `SENIOR_ARCHITECT` | Senior Architect | Yes | `SearchFilter(status="implemented")` |
| `THE_JUDGE` | The Judge (Devil's Advocate) | Yes | `SearchFilter(type="adr")` |
| `DEVOPS_SECOPS` | DevOps & SecOps Agent | Yes | None (full vault) |
| `DIAGRAMMER` | Diagrammer Agent | Yes | None (full vault) |

## Acceptance Criteria

### Scenario 1: NL_INTERPRETER returns formalized request without RAG

```
Given a SubAgentRunner with a mocked LLM returning "Formal: use hexagonal arch"
When SubAgentRunner.run(role=AgentRole.NL_INTERPRETER, user_request="make it cleaner", ...)
Then response.content == "Formal: use hexagonal arch"
And response.context_chunks == []
```

### Scenario 2: SENIOR_ARCHITECT retrieves RAG context filtered by status=implemented

```
Given a document store with implemented and draft chunks
When SubAgentRunner.run(role=AgentRole.SENIOR_ARCHITECT, ...)
Then QueryVault is called with SearchFilter(status="implemented")
And context_chunks contains only implemented chunks
```

### Scenario 3: SubAgentRunner builds prompt including context block

```
Given an agent that uses RAG and QueryVault returns 2 chunks
When SubAgentRunner.run() is called
Then the LLM receives a prompt that includes the chunk content
And the prompt includes the agent's system_prompt
```

### Scenario 4: AgentRole enum has all 6 roles

```
Given AgentRole
When list(AgentRole) is called
Then 6 members are returned
```

### Scenario 5: SubAgentProfile is frozen (immutable)

```
Given a SubAgentProfile instance
When profile.system_prompt = "mutated" is attempted
Then AttributeError is raised
```

### Scenario 6: Diagrammer prompt produces Mermaid block marker

```
Given DIAGRAMMER's system_prompt
When the prompt is inspected
Then it contains the instruction to output a mermaid code block
```

## Implementation Notes

- `AgentRole` → `src/domain/agents/agent_role.py`
- `SubAgentProfile` + profiles → `src/domain/agents/sub_agent_profiles.py`
- `SubAgentRunner` + `SubAgentResponse` → `src/application/agents/sub_agent_runner.py`
- Tests live in `tests/domain/agents/` and `tests/application/agents/`
- Tests mock both `ILLMProvider` and `IDocumentStore` — no real calls
- System prompts are Python string constants (not external files in Phase 3)
