---
created: 2026-09-05
updated: 2026-09-06
type: spec
phase: 1
layer: domain
status: implemented
tags: [port, llm, domain, interface, ai-agent-assistant]
category: meta-project
---

# Feature: Domain Port - ILLMProvider

**As a** system developer
**I want** to define the `ILLMProvider` abstract port in the Domain layer
**So that** Application use cases can invoke LLM completions without depending on any specific provider SDK (OpenAI, Gemini, Anthropic, etc.).

## Context & Motivation

Per ADR-004 (Clean Architecture) and ADR-010 (Multi-Provider Routing), the Domain layer must define **what** it needs from an LLM without knowing **how** it is fulfilled. This port is the contract that every Infrastructure adapter (e.g., `GeminiAdapter`, `OpenAIAdapter`) must implement.

## Port Contract

The `ILLMProvider` interface must expose exactly **one public method**:

```
complete(prompt: str, model_name: str) -> str
```

### Parameters

| Parameter    | Type  | Constraint                                                           |
| :----------- | :---- | :------------------------------------------------------------------- |
| `prompt`     | `str` | Non-empty string. Validated by the Application layer before calling. |
| `model_name` | `str` | Non-empty string. Free-form; chosen by the user per ADR-010.         |

### Return value

A non-empty `str` containing the LLM's textual response.

### Exceptions

| Exception          | When                                                                                                                                         |
| :----------------- | :------------------------------------------------------------------------------------------------------------------------------------------- |
| `LLMProviderError` | Any provider-level failure (network, quota, invalid key). Must be defined in the Domain as a plain Python exception subclassing `Exception`. |

> **Note:** `LLMProviderError` lives in `src/domain/exceptions.py`. Infrastructure adapters **must** catch their SDK-specific exceptions and re-raise them as `LLMProviderError` to preserve the anti-corruption layer.

## Acceptance Criteria

### Scenario 1: Port is abstract — cannot be instantiated directly

```
Given the ILLMProvider class
When ILLMProvider() is instantiated directly
Then a TypeError is raised (ABC enforcement)
```

### Scenario 2: Concrete adapter satisfies the contract

```
Given a class FakeAdapter(ILLMProvider) that implements complete()
When FakeAdapter().complete(prompt="Hello", model_name="fake-model")
Then a non-empty str is returned
And no exception is raised
```

### Scenario 3: Incomplete adapter is rejected

```
Given a class IncompleteAdapter(ILLMProvider) that does NOT implement complete()
When IncompleteAdapter() is instantiated
Then a TypeError is raised (ABC enforcement)
```

## Implementation Notes

- Use Python's `abc.ABC` + `abc.abstractmethod`. **No third-party packages.**
- The port lives at: `src/domain/ports/llm_provider.py`
- `LLMProviderError` lives at: `src/domain/exceptions.py`
- The port defines **only** the interface. No retry logic, no timeout logic — those belong in the Infrastructure adapter.
- Future extension (streaming, embeddings) must be added as **separate methods** on the same port, not as overloads of `complete()`, to keep signatures explicit.
