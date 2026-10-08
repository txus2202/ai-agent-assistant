"""
Application Agent: SupervisorAgent

Orchestrates the ATENEA multi-agent debate flow via a typed async event stream.
Returns an AsyncGenerator[SupervisorEvent, None] — compatible with WebSocket
streaming (Phase 4, ADR-016) and synchronous iteration in tests via asyncio.run().

Debate flow:
  Phase A (architects):
    NL_INTERPRETER → INNOVATOR → SENIOR_ARCHITECT → THE_JUDGE
    HITL ① (APPROVE / REJECT loops architects / REFINE carries feedback)

  Phase B (implementation):
    DIAGRAMMER → DEVOPS_SECOPS
    HITL ② (APPROVE / REJECT loops phase B / REFINE carries feedback)

  Consolidation:
    Final LLM call aggregating all agent outputs → DONE event

ADR-016: Converted to async generator for native WebSocket integration.
ADR-015: No ADK dependency. hitl_callback is now an async callable.
"""
from __future__ import annotations

import asyncio
from typing import Any
from collections.abc import AsyncGenerator, Awaitable, Callable

from src.application.agents.sub_agent_runner import SubAgentRunner
from src.domain.agents.agent_role import AgentRole
from src.domain.agents.supervisor_events import (
    EventType,
    HITLDecision,
    HITLResponse,
    SupervisorEvent,
)
from src.domain.ports.document_store import IDocumentStore
from src.domain.ports.llm_provider import ILLMProvider

# ---------------------------------------------------------------------------
# Prompt template for final consolidation
# ---------------------------------------------------------------------------
_CONSOLIDATION_PROMPT = """\
You are ATENEA, an AI architecture assistant. The following debate has been conducted by your specialist agents.
Produce a single, well-structured Markdown document (200-400 words) that consolidates all perspectives into
a clear, actionable architectural recommendation.

Include:
1. A brief executive summary of the chosen approach.
2. The key design decisions and their rationale.
3. The main risks identified by The Judge, and how the recommendation mitigates them.
4. Next steps for implementation.

--- Debate outputs ---
{debate_context}
"""


class SupervisorAgent:
    """Stateless async orchestrator for the ATENEA multi-agent debate."""

    @staticmethod
    def run(
        user_request: str,
        document_store: IDocumentStore,
        agent_config_repo: Any, # We'll use duck typing or import it if needed
        llm_factory: Callable[[str], ILLMProvider],
        hitl_callback: Callable[[SupervisorEvent], Awaitable[HITLResponse]],
    ) -> AsyncGenerator[SupervisorEvent, None]:
        """
        Run the full debate flow and yield SupervisorEvents asynchronously (ADR-016).

        Args:
            user_request:   The user's architectural question or problem.
            document_store: IDocumentStore for RAG retrieval by sub-agents.
            agent_config_repo: Repository to lookup agent-specific models.
            llm_factory:    Callable to get the ILLMProvider given a provider name.
            hitl_callback:  Async callable invoked at each HITL checkpoint.
                            Returns HITLResponse(decision, feedback).

        Yields:
            SupervisorEvent — one per agent start/complete, HITL checkpoint, and DONE.
        """
        return _debate_generator(
            user_request=user_request,
            document_store=document_store,
            agent_config_repo=agent_config_repo,
            llm_factory=llm_factory,
            hitl_callback=hitl_callback,
        )


async def _debate_generator(
    user_request: str,
    document_store: IDocumentStore,
    agent_config_repo: Any,
    llm_factory: Callable[[str], ILLMProvider],
    hitl_callback: Callable[[SupervisorEvent], Awaitable[HITLResponse]],
) -> AsyncGenerator[SupervisorEvent, None]:
    
    # Setup global defaults if config not found
    from src.presentation.api.config import get_settings
    settings = get_settings()

    async def run_role(r: AgentRole, req: str) -> tuple[AgentRole, str]:
        # Lookup configuration for this specific role
        config = agent_config_repo.find_by_role(r.value)
        
        provider_name = config.provider if config else settings.default_provider
        model_name = config.model_name if config else settings.default_model
        
        # Instantiate the correct provider for this agent
        llm_provider = llm_factory(provider_name)
        
        resp = await SubAgentRunner.run(
            role=r,
            user_request=req,
            llm_provider=llm_provider,
            document_store=document_store,
            model_name=model_name,
        )
        return r, resp.content

    state = DebateState()
    
    async for event in _run_phase_1(state, user_request, run_role, hitl_callback):
        yield event
        
    async for event in _run_phase_2(state, run_role, hitl_callback):
        yield event
        
    async for event in _run_phase_3(state, run_role, hitl_callback):
        yield event
        
    async for event in _run_phase_4(state, run_role):
        yield event
        
    supervisor_config = agent_config_repo.find_by_role(AgentRole.SUPERVISOR.value)
    sup_provider_name = supervisor_config.provider if supervisor_config else settings.default_provider
    sup_model_name = supervisor_config.model_name if supervisor_config else settings.default_model
    
    supervisor_provider = llm_factory(sup_provider_name)
    yield await _run_consolidation(state, supervisor_provider, sup_model_name)


class DebateState:
    def __init__(self) -> None:
        self.agent_outputs: dict[str, str] = {}
        self.formalized: str = ""
        self.selected_solutions: list[str] = []
        self.final_solutions: list[str] = []
        self.hitl2_content: str = ""

async def _run_phase_1(
    state: DebateState,
    user_request: str,
    run_role: Callable[[AgentRole, str], Awaitable[tuple[AgentRole, str]]],
    hitl_callback: Callable[[SupervisorEvent], Awaitable[HITLResponse]]
) -> AsyncGenerator[SupervisorEvent, None]:
    refinement = ""
    while True:
        req = user_request + (f"\n\n## User Refinement\n{refinement}" if refinement else "")
        yield SupervisorEvent(type=EventType.AGENT_STARTED, role=AgentRole.NL_INTERPRETER, content="")
        _, nl_content = await run_role(AgentRole.NL_INTERPRETER, req)
        state.agent_outputs[AgentRole.NL_INTERPRETER.value] = nl_content
        yield SupervisorEvent(
            type=EventType.AGENT_COMPLETED,
            role=AgentRole.NL_INTERPRETER,
            content=nl_content,
        )
        
        hitl_event = SupervisorEvent(
            type=EventType.HITL_REQUIRED,
            role=None,
            content=f"## Interpretation\n{nl_content}",
            metadata={"checkpoint": "1_interpreter"},
        )
        yield hitl_event
        hitl = await hitl_callback(hitl_event)

        if hitl.decision == HITLDecision.APPROVE:
            state.formalized = nl_content
            break
        elif hitl.decision == HITLDecision.REFINE:
            refinement = hitl.feedback

async def _run_phase_2(
    state: DebateState,
    run_role: Callable[[AgentRole, str], Awaitable[tuple[AgentRole, str]]],
    hitl_callback: Callable[[SupervisorEvent], Awaitable[HITLResponse]]
) -> AsyncGenerator[SupervisorEvent, None]:
    refinement = ""
    while True:
        req = state.formalized + (f"\n\n## User Refinement\n{refinement}" if refinement else "")
        roles = (AgentRole.INNOVATOR, AgentRole.SENIOR_ARCHITECT)
        for role in roles:
            yield SupervisorEvent(type=EventType.AGENT_STARTED, role=role, content="")
            
        results = await asyncio.gather(*(run_role(r, req) for r in roles))
        
        for role, content in results:
            state.agent_outputs[role.value] = content
            yield SupervisorEvent(type=EventType.AGENT_COMPLETED, role=role, content=content)

        state.hitl2_content = (
            f"## {AgentRole.INNOVATOR.value}\n{state.agent_outputs[AgentRole.INNOVATOR.value]}\n\n"
            f"## {AgentRole.SENIOR_ARCHITECT.value}\n{state.agent_outputs[AgentRole.SENIOR_ARCHITECT.value]}"
        )
        hitl_event = SupervisorEvent(
            type=EventType.HITL_REQUIRED,
            role=None,
            content=state.hitl2_content,
            metadata={"checkpoint": "2_architects"},
        )
        yield hitl_event
        hitl = await hitl_callback(hitl_event)

        if hitl.decision == HITLDecision.APPROVE:
            state.selected_solutions = hitl.selected_options
            break
        elif hitl.decision == HITLDecision.REFINE:
            refinement = hitl.feedback

async def _run_phase_3(
    state: DebateState,
    run_role: Callable[[AgentRole, str], Awaitable[tuple[AgentRole, str]]],
    hitl_callback: Callable[[SupervisorEvent], Awaitable[HITLResponse]]
) -> AsyncGenerator[SupervisorEvent, None]:
    refinement = ""
    
    proposals_text = ""
    if state.selected_solutions:
        proposals_text = "The user has selected the following options to review:\n" + ", ".join(state.selected_solutions)
        proposals_text += "\n\nRefer to the architecture proposals above and ONLY critique the selected ones."
    else:
        proposals_text = "Review the following proposals:\n\n" + state.hitl2_content

    while True:
        req = state.formalized + "\n\n" + proposals_text + (f"\n\n## User Refinement\n{refinement}" if refinement else "")
        yield SupervisorEvent(type=EventType.AGENT_STARTED, role=AgentRole.THE_JUDGE, content="")
        _, judge_content = await run_role(AgentRole.THE_JUDGE, req)
        state.agent_outputs[AgentRole.THE_JUDGE.value] = judge_content
        yield SupervisorEvent(type=EventType.AGENT_COMPLETED, role=AgentRole.THE_JUDGE, content=judge_content)

        hitl_event = SupervisorEvent(
            type=EventType.HITL_REQUIRED,
            role=None,
            content=f"## {AgentRole.THE_JUDGE.value}\n{judge_content}",
            metadata={"checkpoint": "3_judge"},
        )
        yield hitl_event
        hitl = await hitl_callback(hitl_event)

        if hitl.decision == HITLDecision.APPROVE:
            state.final_solutions = hitl.selected_options or state.selected_solutions
            break
        elif hitl.decision == HITLDecision.REFINE:
            refinement = hitl.feedback

async def _run_phase_4(
    state: DebateState,
    run_role: Callable[[AgentRole, str], Awaitable[tuple[AgentRole, str]]]
) -> AsyncGenerator[SupervisorEvent, None]:
    impl_context = "Selected Final Solutions:\n" + ", ".join(state.final_solutions) if state.final_solutions else state.hitl2_content
    req = state.formalized + "\n\n" + impl_context
    
    roles_impl = (AgentRole.DIAGRAMMER, AgentRole.DEVOPS_SECOPS)
    for role in roles_impl:
        yield SupervisorEvent(type=EventType.AGENT_STARTED, role=role, content="")
        
    results_impl = await asyncio.gather(*(run_role(r, req) for r in roles_impl))
    
    for role, content in results_impl:
        state.agent_outputs[role.value] = content
        yield SupervisorEvent(type=EventType.AGENT_COMPLETED, role=role, content=content)

async def _run_consolidation(
    state: DebateState,
    default_provider: ILLMProvider,
    default_model: str
) -> SupervisorEvent:
    debate_context = "\n\n".join(
        f"### {role}\n{content}" for role, content in state.agent_outputs.items()
    )
    consolidation_prompt = _CONSOLIDATION_PROMPT.format(debate_context=debate_context)
    
    final_response = await asyncio.to_thread(default_provider.complete, consolidation_prompt, default_model)

    return SupervisorEvent(type=EventType.DONE, role=AgentRole.SUPERVISOR, content=final_response)
