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
    async def run(
        user_request: str,
        llm_provider: ILLMProvider,
        document_store: IDocumentStore,
        model_name: str,
        hitl_callback: Callable[[SupervisorEvent], Awaitable[HITLResponse]],
    ) -> AsyncGenerator[SupervisorEvent, None]:
        """
        Run the full debate flow and yield SupervisorEvents asynchronously (ADR-016).

        Args:
            user_request:   The user's architectural question or problem.
            llm_provider:   ILLMProvider for all LLM calls (agents + consolidation).
            document_store: IDocumentStore for RAG retrieval by sub-agents.
            model_name:     Model used for all LLM calls.
            hitl_callback:  Async callable invoked at each HITL checkpoint.
                            Returns HITLResponse(decision, feedback).

        Yields:
            SupervisorEvent — one per agent start/complete, HITL checkpoint, and DONE.
        """
        return _debate_generator(
            user_request=user_request,
            llm_provider=llm_provider,
            document_store=document_store,
            model_name=model_name,
            hitl_callback=hitl_callback,
        )


async def _debate_generator(
    user_request: str,
    llm_provider: ILLMProvider,
    document_store: IDocumentStore,
    model_name: str,
    hitl_callback: Callable[[SupervisorEvent], Awaitable[HITLResponse]],
) -> AsyncGenerator[SupervisorEvent, None]:
    # ── Phase A: NL_INTERPRETER ───────────────────────────────────────
    yield SupervisorEvent(type=EventType.AGENT_STARTED, role=AgentRole.NL_INTERPRETER, content="")
    nl_resp = await SubAgentRunner.run(
        role=AgentRole.NL_INTERPRETER,
        user_request=user_request,
        llm_provider=llm_provider,
        document_store=document_store,
        model_name=model_name,
    )
    yield SupervisorEvent(
        type=EventType.AGENT_COMPLETED,
        role=AgentRole.NL_INTERPRETER,
        content=nl_resp.content,
    )
    formalized = nl_resp.content
    refinement = ""

    # ── Phase A: Architect loop (REJECT loops, REFINE breaks with feedback)
    agent_outputs: dict[str, str] = {}

    while True:
        augmented = formalized + (f"\n\n## User Refinement\n{refinement}" if refinement else "")

        for role in (AgentRole.INNOVATOR, AgentRole.SENIOR_ARCHITECT, AgentRole.THE_JUDGE):
            yield SupervisorEvent(type=EventType.AGENT_STARTED, role=role, content="")
            resp = await SubAgentRunner.run(
                role=role,
                user_request=augmented,
                llm_provider=llm_provider,
                document_store=document_store,
                model_name=model_name,
            )
            agent_outputs[role.value] = resp.content
            yield SupervisorEvent(type=EventType.AGENT_COMPLETED, role=role, content=resp.content)

        # HITL ①
        hitl1_content = (
            f"## {AgentRole.INNOVATOR.value}\n{agent_outputs[AgentRole.INNOVATOR.value]}\n\n"
            f"## {AgentRole.SENIOR_ARCHITECT.value}\n{agent_outputs[AgentRole.SENIOR_ARCHITECT.value]}\n\n"
            f"## {AgentRole.THE_JUDGE.value}\n{agent_outputs[AgentRole.THE_JUDGE.value]}"
        )
        hitl1_event = SupervisorEvent(
            type=EventType.HITL_REQUIRED,
            role=None,
            content=hitl1_content,
            metadata={"checkpoint": "1"},
        )
        yield hitl1_event
        hitl1 = await hitl_callback(hitl1_event)

        if hitl1.decision == HITLDecision.APPROVE:
            break
        elif hitl1.decision == HITLDecision.REFINE:
            refinement = hitl1.feedback
            break
        # else REJECT: loop — re-run architects

    # ── Phase B: Implementation loop ─────────────────────────────────
    impl_request = formalized + (f"\n\n## User Refinement\n{refinement}" if refinement else "")

    while True:
        for role in (AgentRole.DIAGRAMMER, AgentRole.DEVOPS_SECOPS):
            yield SupervisorEvent(type=EventType.AGENT_STARTED, role=role, content="")
            resp = await SubAgentRunner.run(
                role=role,
                user_request=impl_request,
                llm_provider=llm_provider,
                document_store=document_store,
                model_name=model_name,
            )
            agent_outputs[role.value] = resp.content
            yield SupervisorEvent(type=EventType.AGENT_COMPLETED, role=role, content=resp.content)

        # HITL ②
        hitl2_content = (
            f"## {AgentRole.DIAGRAMMER.value}\n{agent_outputs[AgentRole.DIAGRAMMER.value]}\n\n"
            f"## {AgentRole.DEVOPS_SECOPS.value}\n{agent_outputs[AgentRole.DEVOPS_SECOPS.value]}"
        )
        hitl2_event = SupervisorEvent(
            type=EventType.HITL_REQUIRED,
            role=None,
            content=hitl2_content,
            metadata={"checkpoint": "2"},
        )
        yield hitl2_event
        hitl2 = await hitl_callback(hitl2_event)

        if hitl2.decision == HITLDecision.APPROVE:
            break
        elif hitl2.decision == HITLDecision.REFINE:
            impl_request += f"\n\n## User Refinement\n{hitl2.feedback}"
            break
        # else REJECT: loop — re-run diagrammer + devops

    # ── Consolidation ─────────────────────────────────────────────────
    debate_context = "\n\n".join(
        f"### {role}\n{content}" for role, content in agent_outputs.items()
    )
    consolidation_prompt = _CONSOLIDATION_PROMPT.format(debate_context=debate_context)
    final_response = await asyncio.to_thread(llm_provider.complete, consolidation_prompt, model_name)

    yield SupervisorEvent(type=EventType.DONE, role=None, content=final_response)
