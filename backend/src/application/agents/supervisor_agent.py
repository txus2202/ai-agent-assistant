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

    agent_outputs: dict[str, str] = {}
    
    # ── Phase 1: Interpretation ───────────────────────────────────────
    refinement_1 = ""
    while True:
        req_1 = user_request + (f"\n\n## User Refinement\n{refinement_1}" if refinement_1 else "")
        yield SupervisorEvent(type=EventType.AGENT_STARTED, role=AgentRole.NL_INTERPRETER, content="")
        _, nl_content = await run_role(AgentRole.NL_INTERPRETER, req_1)
        agent_outputs[AgentRole.NL_INTERPRETER.value] = nl_content
        yield SupervisorEvent(
            type=EventType.AGENT_COMPLETED,
            role=AgentRole.NL_INTERPRETER,
            content=nl_content,
        )
        
        hitl1_event = SupervisorEvent(
            type=EventType.HITL_REQUIRED,
            role=None,
            content=f"## Interpretation\n{nl_content}",
            metadata={"checkpoint": "1_interpreter"},
        )
        yield hitl1_event
        hitl1 = await hitl_callback(hitl1_event)

        if hitl1.decision == HITLDecision.APPROVE:
            formalized = nl_content
            break
        elif hitl1.decision == HITLDecision.REFINE:
            refinement_1 = hitl1.feedback
        # else REJECT: loop

    # ── Phase 2: Ideation ──────────────────────────────────────────────
    refinement_2 = ""
    selected_solutions = []
    while True:
        req_2 = formalized + (f"\n\n## User Refinement\n{refinement_2}" if refinement_2 else "")
        roles_step2 = (AgentRole.INNOVATOR, AgentRole.SENIOR_ARCHITECT)
        for role in roles_step2:
            yield SupervisorEvent(type=EventType.AGENT_STARTED, role=role, content="")
            
        results_step2 = await asyncio.gather(*(run_role(r, req_2) for r in roles_step2))
        
        for role, content in results_step2:
            agent_outputs[role.value] = content
            yield SupervisorEvent(type=EventType.AGENT_COMPLETED, role=role, content=content)

        hitl2_content = (
            f"## {AgentRole.INNOVATOR.value}\n{agent_outputs[AgentRole.INNOVATOR.value]}\n\n"
            f"## {AgentRole.SENIOR_ARCHITECT.value}\n{agent_outputs[AgentRole.SENIOR_ARCHITECT.value]}"
        )
        hitl2_event = SupervisorEvent(
            type=EventType.HITL_REQUIRED,
            role=None,
            content=hitl2_content,
            metadata={"checkpoint": "2_architects"},
        )
        yield hitl2_event
        hitl2 = await hitl_callback(hitl2_event)

        if hitl2.decision == HITLDecision.APPROVE:
            selected_solutions = hitl2.selected_options
            break
        elif hitl2.decision == HITLDecision.REFINE:
            refinement_2 = hitl2.feedback
        # else REJECT: loop

    # ── Phase 3: Critique ──────────────────────────────────────────────
    refinement_3 = ""
    final_solutions = []
    
    # Extract only the selected options or fallback to all proposals
    proposals_text = ""
    if selected_solutions:
        proposals_text = "The user has selected the following options to review:\n" + ", ".join(selected_solutions)
        proposals_text += "\n\nRefer to the architecture proposals above and ONLY critique the selected ones."
    else:
        proposals_text = "Review the following proposals:\n\n" + hitl2_content

    while True:
        req_3 = formalized + "\n\n" + proposals_text + (f"\n\n## User Refinement\n{refinement_3}" if refinement_3 else "")
        yield SupervisorEvent(type=EventType.AGENT_STARTED, role=AgentRole.THE_JUDGE, content="")
        _, judge_content = await run_role(AgentRole.THE_JUDGE, req_3)
        agent_outputs[AgentRole.THE_JUDGE.value] = judge_content
        yield SupervisorEvent(type=EventType.AGENT_COMPLETED, role=AgentRole.THE_JUDGE, content=judge_content)

        hitl3_event = SupervisorEvent(
            type=EventType.HITL_REQUIRED,
            role=None,
            content=f"## {AgentRole.THE_JUDGE.value}\n{judge_content}",
            metadata={"checkpoint": "3_judge"},
        )
        yield hitl3_event
        hitl3 = await hitl_callback(hitl3_event)

        if hitl3.decision == HITLDecision.APPROVE:
            final_solutions = hitl3.selected_options or selected_solutions
            break
        elif hitl3.decision == HITLDecision.REFINE:
            refinement_3 = hitl3.feedback
        # else REJECT: loop

    # ── Phase 4: Implementation ────────────────────────────────────────
    refinement_4 = ""
    while True:
        impl_context = "Selected Final Solutions:\n" + ", ".join(final_solutions) if final_solutions else hitl2_content
        req_4 = formalized + "\n\n" + impl_context + (f"\n\n## User Refinement\n{refinement_4}" if refinement_4 else "")
        
        roles_impl = (AgentRole.DIAGRAMMER, AgentRole.DEVOPS_SECOPS)
        for role in roles_impl:
            yield SupervisorEvent(type=EventType.AGENT_STARTED, role=role, content="")
            
        results_impl = await asyncio.gather(*(run_role(r, req_4) for r in roles_impl))
        
        for role, content in results_impl:
            agent_outputs[role.value] = content
            yield SupervisorEvent(type=EventType.AGENT_COMPLETED, role=role, content=content)

        break # No HITL here, just proceed to consolidation

    # ── Consolidation ─────────────────────────────────────────────────
    debate_context = "\n\n".join(
        f"### {role}\n{content}" for role, content in agent_outputs.items()
    )
    consolidation_prompt = _CONSOLIDATION_PROMPT.format(debate_context=debate_context)
    
    # Consolidation uses the default model
    default_provider = llm_factory(settings.default_provider)
    final_response = await asyncio.to_thread(default_provider.complete, consolidation_prompt, settings.default_model)

    yield SupervisorEvent(type=EventType.DONE, role=None, content=final_response)
