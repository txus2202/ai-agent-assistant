---
created: 2026-09-15
updated: 2026-11-23
type: spec
phase: 3
layer: infrastructure
status: implemented
tags: [llm, adapters, gemini, openai, anthropic, local, ollama, provider, registry, infrastructure, ai-agent-assistant]
category: meta-project
---

# Feature: LLM Provider Adapters & Registry

**As a** system developer
**I want** concrete implementations of `ILLMProvider` for Gemini, OpenAI, Anthropic, and Local AI (Ollama)
**So that** any agent in the system can call any cloud or local LLM provider transparently, with all SDK-specific details hidden behind the port.

## Context & Motivation

Phase 1 defined `ILLMProvider` and `RunAgentTask` already routes by `agent.provider` field (ADR-010). Phase 3+ provides the actual Infrastructure adapters and an Application-layer `LLMProviderRegistry` that wires them together.

Per ADR-004, all SDK exceptions must be caught at the adapter boundary and re-raised as `LLMProviderError` — the domain never knows about `google.api_core.exceptions`, `openai.APIError`, or `anthropic.APIError`.

## Adapter Contract

All adapters implement `ILLMProvider.complete(prompt: str, model_name: str) -> str`.

| Adapter | SDK | Env var | Default model |
|---|---|---|---|
| `GeminiAdapter` | `google-genai` | `GEMINI_API_KEY` / `GOOGLE_CLOUD_PROJECT` | `gemini-3.6-flash` |
| `OpenAIAdapter` | `openai` | `OPENAI_API_KEY` | `gpt-4o-mini` |
| `AnthropicAdapter` | `anthropic` | `ANTHROPIC_API_KEY` | `claude-3-5-sonnet-latest` |
| `LocalLLMAdapter` | `openai` (OpenAI-compatible `/v1`) | `LOCAL_LLM_BASE_URL` (or `OLLAMA_BASE_URL`) + optional `LOCAL_LLM_API_KEY` (defaults to `"ollama"`) | Any installed Ollama model (e.g. `llama3.3`, `qwen2.5-coder`) |

## LLMProviderRegistry

Application-layer service that maps `provider: str` → `ILLMProvider` instance.

```python
registry = LLMProviderRegistry()
registry.register("gemini", GeminiAdapter())
registry.register("openai", OpenAIAdapter())

provider = registry.get("gemini")   # → GeminiAdapter
```

- `register(name, adapter)` — registers an adapter under a string key
- `get(name) → ILLMProvider` — raises `ProviderNotFoundError` for unknown keys
- `available() → list[str]` — returns registered provider names

`ProviderNotFoundError` lives in `src/domain/exceptions.py`.

## Acceptance Criteria

### Scenario 1: GeminiAdapter wraps SDK exceptions as LLMProviderError

```
Given a GeminiAdapter configured with an invalid API key
When complete() is called
Then LLMProviderError is raised (not the SDK-specific exception)
```

### Scenario 2: OpenAIAdapter wraps SDK exceptions as LLMProviderError

```
Given an OpenAIAdapter configured with an invalid API key
When complete() is called
Then LLMProviderError is raised
```

### Scenario 3: AnthropicAdapter wraps SDK exceptions as LLMProviderError

```
Given an AnthropicAdapter configured with an invalid API key
When complete() is called
Then LLMProviderError is raised
```

### Scenario 4: Registry returns correct adapter by provider name

```
Given a LLMProviderRegistry with "gemini" → GeminiAdapter registered
When registry.get("gemini") is called
Then a GeminiAdapter instance is returned
```

### Scenario 5: Registry raises ProviderNotFoundError for unknown provider

```
Given a LLMProviderRegistry with only "gemini" registered
When registry.get("openai") is called
Then ProviderNotFoundError is raised with a descriptive message
```

### Scenario 6: Registry.available() returns all registered names

```
Given a registry with "gemini" and "openai" registered
When registry.available() is called
Then ["gemini", "openai"] is returned (order not guaranteed)
```

### Scenario 7: Adapters are tested with mocked SDKs (no real API calls)

```
Given a patched SDK client that returns "Mocked response"
When GeminiAdapter.complete(prompt="Hello", model_name="gemini-1.5-flash") is called
Then "Mocked response" is returned
And no real network request is made
```

## Implementation Notes

- Adapters live at: `src/infrastructure/llm/`
  - `gemini_adapter.py`
  - `openai_adapter.py`
  - `anthropic_adapter.py`
  - `local_llm_adapter.py` (`LocalLLMAdapter` registered under provider key `"local"`)
- `LocalLLMAdapter` specifics:
  - Activated ONLY when `LOCAL_LLM_BASE_URL` (or `OLLAMA_BASE_URL`) is set in `.env` / environment. If empty/unset, `is_provider_configured("local")` returns `False` and `"local"` is not registered or shown in the UI.
  - Normalizes `base_url` automatically so both `http://localhost:11434` and `http://localhost:11434/v1` target the OpenAI-compatible `/v1` endpoint exposed by Ollama.
  - Uses `LOCAL_LLM_API_KEY` if provided, or defaults to `"ollama"` (since local Ollama requires no real secret key).
  - `list_models(probe=...)` queries `/v1/models` on the local Ollama server and filters out pure embedding models (`embed`, `minilm`, `bge-`, `nomic-embed`) without triggering token-generation probes that would force Ollama to load/unload every installed model into RAM/VRAM.
- `LLMProviderRegistry` lives at: `src/application/services/llm_provider_registry.py`
- `ProviderNotFoundError` added to `src/domain/exceptions.py`
- Tests mock the SDK client — never call real APIs in test suite
- Each adapter reads its API key / base URL from env var in `__init__`; raises `LLMProviderError` immediately if required config is missing
