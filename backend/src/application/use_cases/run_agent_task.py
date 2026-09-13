"""
Application Use Case: RunAgentTask

Orchestrates the execution of a Task by delegating the LLM call to the
appropriate provider adapter. Zero framework imports — pure Python stdlib only.

Spec: obsidian_vault/docs/features/feature_run_agent_task.md
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from src.domain.exceptions import AgentNotFoundError, LLMProviderError, ProviderNotRegisteredError
from src.domain.entities.task import Task
from src.domain.ports.agent_repository import IAgentRepository
from src.domain.ports.llm_provider import ILLMProvider


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RunAgentTaskInput:
    """Immutable input contract for the RunAgentTask use case."""
    agent_id: uuid.UUID
    prompt: str


@dataclass(frozen=True)
class RunAgentTaskOutput:
    """Immutable output contract for the RunAgentTask use case."""
    task_id: uuid.UUID
    result: str
    status: Literal["completed", "failed"]


# ---------------------------------------------------------------------------
# Use case
# ---------------------------------------------------------------------------

class RunAgentTask:
    """
    Core use case: execute a prompt via a configured Agent.

    Constructor injection (no service locator, no global state):
    - ``agent_repository``: used to look up the assigned Agent.
    - ``llm_providers``: registry mapping provider names (e.g. "gemini",
      "openai") to their ``ILLMProvider`` adapter instances.

    Phase 1 note: the ``Task`` entity is created in-memory and NOT persisted.
    ``ITaskRepository`` will be introduced in Phase 2 (ADR-011).
    """

    def __init__(
        self,
        agent_repository: IAgentRepository,
        llm_providers: dict[str, ILLMProvider],
    ) -> None:
        self._repo = agent_repository
        self._providers = llm_providers

    def execute(self, input_data: RunAgentTaskInput) -> RunAgentTaskOutput:
        """
        Run the use case.

        Args:
            input_data: Validated input DTO with ``agent_id`` and ``prompt``.

        Returns:
            ``RunAgentTaskOutput`` with ``status="completed"`` on success or
            ``status="failed"`` when the LLM call raises ``LLMProviderError``.

        Raises:
            ValueError: If ``prompt`` is empty/whitespace or the agent's
                provider has no registered adapter.
            AgentNotFoundError: If no Agent with the given ``agent_id`` exists.
        """
        # 1. Validate prompt (fail fast before hitting the repository)
        if not input_data.prompt or not input_data.prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        # 2. Retrieve Agent
        agent = self._repo.find_by_id(input_data.agent_id)
        if agent is None:
            raise AgentNotFoundError(input_data.agent_id)

        # 3. Resolve provider adapter
        provider = self._providers.get(agent.provider)
        if provider is None:
            raise ProviderNotRegisteredError(
                provider=agent.provider,
                available=list(self._providers.keys()),
            )

        # 4. Create and start task
        task = Task(prompt=input_data.prompt, agent_id=agent.id)
        task.mark_as_running()

        # 5. Execute LLM call — graceful degradation on failure
        try:
            llm_response = provider.complete(
                prompt=task.prompt,
                model_name=agent.model_name,
            )
            task.mark_as_completed(result=llm_response)
            assert task.result is not None  # guaranteed by mark_as_completed
            return RunAgentTaskOutput(
                task_id=task.id,
                result=task.result,
                status="completed",
            )
        except LLMProviderError as exc:
            task.mark_as_failed(reason=str(exc))
            assert task.result is not None  # guaranteed by mark_as_failed
            return RunAgentTaskOutput(
                task_id=task.id,
                result=task.result,
                status="failed",
            )
