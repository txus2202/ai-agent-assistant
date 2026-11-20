---
type: feature_spec
status: implemented
created: 2026-09-19
tags: [backend, config, phase4, ai-agent-assistant]
category: meta-project
---

# Feature: Agent Model Configuration

## 1. Description
Allow individual configuration of the LLM provider and model for each agent in the ATENEA system, rather than relying on a single global default.

## 2. Requirements
- The system must persist the `provider` and `model_name` for each `AgentRole`.
- The configuration must be stored in SQLite (`agent_configs` table).
- The REST API must expose `GET /config/agents` to retrieve all configurations.
- The REST API must expose `PUT /config/agents/{role}` to update a specific agent's configuration.
- The `SupervisorAgent` and WebSockets must use the stored configuration when instantiating the LLM provider for a specific sub-agent.

## 3. Architecture
- **Domain**: `AgentConfig` value object, `IAgentConfigRepository` port.
- **Infrastructure**: `SqliteAgentConfigRepository` adapter.
- **Presentation**: `routes/config.py` endpoints. `debate.py` WS route injecting the repository into `SupervisorAgent.run`.

## 4. Test Plan (TDD)
- `test_agent_config_repository.py`: Verify CRUD operations on SQLite.
- `test_config_api.py`: Verify `GET` and `PUT` endpoints return correct status codes and data.
- `test_supervisor_agent.py`: Verify `SupervisorAgent` calls the repository and injects the correct `llm_provider` to `SubAgentRunner`.
