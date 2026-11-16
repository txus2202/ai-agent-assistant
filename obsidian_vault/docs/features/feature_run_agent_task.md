---
created: 2026-09-05
updated: 2026-09-06
type: spec
phase: 1
layer: application
status: implemented
tags: [use-case, agent, task, application, ai-agent-assistant]
---

# Feature: Use Case - RunAgentTask

**As a** CLI user
**I want** to submit a text prompt that gets processed by a configured Agent
**So that** I receive an LLM-generated response routed through the agent's assigned provider and model.

## Context & Motivation

This is the **core use case** of Phase 1 — the minimum viable execution unit. It orchestrates the Domain entities (`Agent`, `Task`) and Domain ports (`IAgentRepository`, `ILLMProvider`) inside the Application layer, with zero framework imports.

## Preconditions

- At least one `Agent` has been previously saved in the repository.
- The `ILLMProvider` for that agent's `provider` is available and configured.

## Use Case: `RunAgentTask`

**Input DTO:**

```python
@dataclass(frozen=True)
class RunAgentTaskInput:
    agent_id: UUID
    prompt: str
```

**Output DTO:**

```python
@dataclass(frozen=True)
class RunAgentTaskOutput:
    task_id: UUID
    result: str
    status: str  # "completed" | "failed"
```

## Main Flow (Happy Path)

```
1. Validate input: agent_id is a valid UUID, prompt is non-empty.
2. Retrieve Agent from IAgentRepository by agent_id.
   → If not found: raise AgentNotFoundError(agent_id).
3. Create a new Task(prompt=prompt, agent_id=agent_id).
4. Call task.mark_as_running().
5. Call ILLMProvider.complete(prompt=task.prompt, model_name=agent.model_name).
6. Call task.mark_as_completed(result=llm_response).
7. Return RunAgentTaskOutput(task_id=task.id, result=task.result, status="completed").
```

## Alternative Flow: LLM Failure

```
5a. ILLMProvider.complete() raises LLMProviderError.
    → Call task.mark_as_failed(reason=str(error)).
    → Return RunAgentTaskOutput(task_id=task.id, result=task.result, status="failed").
    [Do NOT re-raise — the use case handles the failure gracefully and returns a structured output.]
```

## Acceptance Criteria

### Scenario 1: Successful task execution (Happy Path)

```
Given a saved Agent(provider="fake", model_name="fake-v1")
And   a FakeLLMProvider that returns "42" for any prompt
When  RunAgentTask(agent_id=agent.id, prompt="What is the answer?") is executed
Then  output.status == "completed"
And   output.result == "42"
And   output.task_id is a UUID
```

### Scenario 2: Agent not found

```
Given an empty repository
When  RunAgentTask(agent_id=some_uuid, prompt="Hello") is executed
Then  AgentNotFoundError is raised
And   the error message references the unknown agent_id
```

### Scenario 3: LLM provider failure — graceful degradation

```
Given a saved Agent
And   a FakeLLMProvider that raises LLMProviderError("quota exceeded")
When  RunAgentTask(agent_id=agent.id, prompt="Hello") is executed
Then  output.status == "failed"
And   output.result contains "quota exceeded"
And   no exception propagates to the caller
```

### Scenario 4: Empty prompt is rejected

```
Given a saved Agent
When  RunAgentTask(agent_id=agent.id, prompt="   ") is executed
Then  a ValueError is raised with message "Prompt cannot be empty"
```

### Scenario 5: Provider not registered (gap detected during implementation)

```
Given a saved Agent with provider="openai"
And   only a "gemini" adapter is registered in the provider registry
When  RunAgentTask(agent_id=agent.id, prompt="Hello") is executed
Then  a ValueError is raised with message "No LLM provider registered for 'openai'"
```

## Implementation Notes

- **File:** `src/application/use_cases/run_agent_task.py`
- **Domain exceptions used:**
  - `AgentNotFoundError(agent_id: UUID)` → `src/domain/exceptions.py`
  - `LLMProviderError` → `src/domain/exceptions.py`
- **Constructor injection:** `RunAgentTask` receives `IAgentRepository` and `ILLMProvider` at construction time. No global state, no service locator.
- **No framework imports:** `dataclass` from `dataclasses` (stdlib) is allowed.
- **Task persistence:** For Phase 1, the `Task` entity is created in-memory and **not** persisted (no `ITaskRepository` yet). Phase 2 will introduce task history storage.
- **Provider routing:** The Application layer selects the correct `ILLMProvider` adapter based on `agent.provider`. Phase 1 can use a simple `dict[str, ILLMProvider]` registry injected at construction time.
