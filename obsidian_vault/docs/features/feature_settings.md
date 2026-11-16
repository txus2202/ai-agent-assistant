---
created: 2026-09-17
updated: 2026-09-17
type: spec
phase: 4
layer: presentation
status: draft
tags: [settings, api-keys, configuration, models, env, ai-agent-assistant]
---

# Feature: Settings — API Keys & Model Configuration

**As a** user
**I want** to configure my API keys and select the default LLM model per provider
**So that** I can switch between Gemini, OpenAI, and Anthropic without restarting the server.

## Context & Motivation

API keys are stored in `.env` (consistent with current approach — no new secrets infrastructure). The Settings panel allows runtime update of these values. The server reloads the `LLMProviderRegistry` after any change.

Available models per provider are fetched dynamically from the provider's API, with a hardcoded fallback list if the API call fails.

## REST Endpoints

### `GET /settings`

Returns current configuration. API keys are **masked** (`***`) for security.

```json
{
  "providers": {
    "gemini":    { "configured": true,  "key_masked": "AIza***...***Xk9" },
    "openai":    { "configured": false, "key_masked": "" },
    "anthropic": { "configured": false, "key_masked": "" }
  },
  "default_provider": "gemini",
  "default_model": "gemini-1.5-flash",
  "rag_top_k": 5
}
```

### `PUT /settings`

Updates one or more settings. Persists to `.env` and hot-reloads the registry.

```json
// Request body (all fields optional):
{
  "gemini_api_key":    "AIza...",
  "openai_api_key":    "sk-...",
  "anthropic_api_key": "sk-ant-...",
  "default_provider":  "gemini",
  "default_model":     "gemini-1.5-flash",
  "rag_top_k":         5
}

// Response 200:
{ "ok": true }

// Response 422 (invalid provider):
{ "detail": "Unknown provider: 'cohere'" }
```

### `GET /models/{provider}`

Returns the list of available models for the given provider. First tries the provider's SDK, falls back to a hardcoded list.

```json
// GET /models/gemini
{
  "provider": "gemini",
  "models": [
    "gemini-1.5-flash",
    "gemini-1.5-pro",
    "gemini-2.0-flash"
  ],
  "source": "api"   // or "fallback"
}
```

Hardcoded fallbacks:

| Provider | Fallback models |
|---|---|
| `gemini` | `gemini-1.5-flash`, `gemini-1.5-pro`, `gemini-2.0-flash` |
| `openai` | `gpt-4o-mini`, `gpt-4o`, `gpt-4-turbo` |
| `anthropic` | `claude-3-haiku-20240307`, `claude-3-5-sonnet-20241022`, `claude-3-opus-20240229` |

## `.env` Persistence Strategy

`PUT /settings` rewrites the `.env` file in-place:
1. Read current `.env` content.
2. Update matching keys (add if missing, update if present).
3. Write atomically (write to `.env.tmp`, then rename to `.env`).
4. Reload `Settings` from the new file.
5. Re-initialize the `LLMProviderRegistry` with updated adapters.

## Acceptance Criteria

### Scenario 1: GET /settings masks keys correctly

```
Given GEMINI_API_KEY=AIzaXXXXXXXXXXXX in .env
When GET /settings
Then gemini.key_masked starts with "AIza" and ends with the last 4 chars
And the full key is never returned
```

### Scenario 2: PUT /settings updates .env and reloads registry

```
Given openai_api_key not configured
When PUT /settings { "openai_api_key": "sk-test123" }
Then .env file contains OPENAI_API_KEY=sk-test123
And GET /settings shows openai.configured = true
And LLMProviderRegistry.get("openai") no longer raises ProviderNotRegisteredError
```

### Scenario 3: GET /models/gemini with no API key returns fallback

```
Given no GEMINI_API_KEY configured
When GET /models/gemini
Then { models: [...], source: "fallback" }
And HTTP 200 (not an error)
```

### Scenario 4: GET /models/{unknown_provider} returns 404

```
When GET /models/cohere
Then 404 { "detail": "Unknown provider: cohere" }
```

### Scenario 5: PUT /settings with invalid provider returns 422

```
When PUT /settings { "default_provider": "cohere" }
Then 422 { "detail": "Unknown provider: 'cohere'" }
```

## Implementation Notes

- Routes → `src/presentation/api/routes/settings.py` + `src/presentation/api/routes/models.py`
- `.env` atomic write uses `tempfile` + `os.replace()` for safety
- `LLMProviderRegistry` is a singleton injected via FastAPI dependency
- No API key validation at save time — validation happens at first use (consistent with Phase 3 adapters)
- The `key_masked` format: first 4 chars + `***` + last 4 chars, or `""` if not configured
