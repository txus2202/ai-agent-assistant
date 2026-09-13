---
created: 2026-09-05
updated: 2026-09-05
type: spec
phase: 1
layer: domain
status: implemented
tags: [entity, agent, domain]
---

# Feature: Core Entity - Agent

**As a** system developer
**I want** to define the `Agent` domain entity
**So that** I can represent system specialists independently of the underlying AI framework.

## Business Rules (Invariant Validations)

An `Agent` in our domain must contain:

- `id`: Unique identifier (UUID).
- `name`: Name of the specialist. Must be at least 3 characters long.
- `role`: Description of their role. Cannot be empty or whitespace.
- `provider`: The LLM provider chosen by the user (e.g., 'openai', 'gemini', 'anthropic'). Cannot be empty.
- `model_name`: The specific model version chosen by the user (e.g., 'gpt-4o', 'gemini-1.5-pro'). Cannot be empty.
- `status`: Current state (`IDLE`, `THINKING`, `ERROR`). Defaults to `IDLE`.
