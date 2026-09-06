"""
RED tests for the RunAgentTask application use case.

Spec: obsidian_vault/docs/features/feature_run_agent_task.md
Phase: 1 | Layer: Application
"""
import uuid

import pytest

from src.application.use_cases.run_agent_task import RunAgentTask, RunAgentTaskInput
from src.domain.entities.agent import Agent
from src.domain.exceptions import AgentNotFoundError, ProviderNotRegisteredError
from src.infrastructure.persistence.in_memory_agent_repository import (
    InMemoryAgentRepository,
)
from tests.doubles import FailingProvider, FixedResponseProvider



# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_agent(provider: str = "fake") -> Agent:
    return Agent(
        name="Annotator",
        role="Documentation specialist",
        provider=provider,
        model_name="fake-v1",
    )


def _make_use_case(
    agent: Agent | None = None,
    provider_response: str = "42",
    failing_provider: bool = False,
) -> tuple[RunAgentTask, Agent]:
    repo = InMemoryAgentRepository()
    target_agent = agent or _make_agent()
    repo.save(target_agent)

    llm = (
        FailingProvider("quota exceeded")
        if failing_provider
        else FixedResponseProvider(provider_response)
    )

    use_case = RunAgentTask(
        agent_repository=repo,
        llm_providers={"fake": llm},
    )
    return use_case, target_agent


# ---------------------------------------------------------------------------
# Scenario 1: Successful task execution (Happy Path)
# ---------------------------------------------------------------------------

def test_run_agent_task_returns_completed_output() -> None:
    use_case, agent = _make_use_case(provider_response="42")

    output = use_case.execute(RunAgentTaskInput(agent_id=agent.id, prompt="What is the answer?"))

    assert output.status == "completed"
    assert output.result == "42"
    assert isinstance(output.task_id, uuid.UUID)


# ---------------------------------------------------------------------------
# Scenario 2: Agent not found
# ---------------------------------------------------------------------------

def test_run_agent_task_raises_when_agent_not_found() -> None:
    repo = InMemoryAgentRepository()
    use_case = RunAgentTask(
        agent_repository=repo,
        llm_providers={"fake": FixedResponseProvider("irrelevant")},
    )
    unknown_id = uuid.uuid4()

    with pytest.raises(AgentNotFoundError) as exc_info:
        use_case.execute(RunAgentTaskInput(agent_id=unknown_id, prompt="Hello"))

    assert str(unknown_id) in str(exc_info.value)


# ---------------------------------------------------------------------------
# Scenario 3: LLM provider failure — graceful degradation
# ---------------------------------------------------------------------------

def test_run_agent_task_returns_failed_output_on_llm_error() -> None:
    use_case, agent = _make_use_case(failing_provider=True)

    output = use_case.execute(RunAgentTaskInput(agent_id=agent.id, prompt="Hello"))

    assert output.status == "failed"
    assert "quota exceeded" in output.result


# ---------------------------------------------------------------------------
# Scenario 4: Empty prompt is rejected
# ---------------------------------------------------------------------------

def test_run_agent_task_raises_on_empty_prompt() -> None:
    use_case, agent = _make_use_case()

    with pytest.raises(ValueError, match="Prompt cannot be empty"):
        use_case.execute(RunAgentTaskInput(agent_id=agent.id, prompt="   "))


# ---------------------------------------------------------------------------
# Scenario 5 (gap detected): Provider not registered in the registry
# ---------------------------------------------------------------------------

def test_run_agent_task_raises_when_provider_not_registered() -> None:
    """
    If an Agent has provider='openai' but no OpenAI adapter was injected,
    the use case must raise ProviderNotRegisteredError (config error, not
    input validation error) with the missing provider name accessible.
    """
    repo = InMemoryAgentRepository()
    agent = _make_agent(provider="openai")
    repo.save(agent)

    use_case = RunAgentTask(
        agent_repository=repo,
        llm_providers={"gemini": FixedResponseProvider("irrelevant")},  # openai missing
    )

    with pytest.raises(ProviderNotRegisteredError) as exc_info:
        use_case.execute(RunAgentTaskInput(agent_id=agent.id, prompt="Hello"))

    assert exc_info.value.provider == "openai"
    assert "gemini" in exc_info.value.available
