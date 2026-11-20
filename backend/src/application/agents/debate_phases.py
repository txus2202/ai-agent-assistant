"""
Application Agent Helpers: Debate Phase Loops & Parallel Stage Runners

Provides the unified parameterized HITL phase loop (`run_hitl_phase_loop`),
parallel role round execution helpers, and reviewer/evaluator prompt builders.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable

from src.application.agents.debate_state import (
    ERROR_MARKER,
    FAILURE_MARKER,
    SECTION_SEPARATOR,
    DebateState,
)
from src.domain.agents.supervisor_events import (
    EventType,
    HITLDecision,
    HITLResponse,
    SupervisorEvent,
)
from src.domain.ports.agent_catalog_repository import IAgentCatalogRepository

logger = logging.getLogger(__name__)

RoleRunner = Callable[[str, str], Awaitable[tuple[str, str]]]
HitlCallback = Callable[[SupervisorEvent], Awaitable[HITLResponse]]


def constant_prompt(prompt: str) -> Callable[[str], str]:
    """Return a single-argument prompt builder returning ``prompt`` for any role."""

    def _build(_role: str) -> str:
        return prompt

    return _build


async def execute_role_safely(
    role: str,
    req: str,
    run_role: RoleRunner,
    agent_catalog: IAgentCatalogRepository | None = None,
) -> tuple[str, str, str | None]:
    """Execute ``run_role`` catching exceptions to allow graceful degradation."""
    try:
        agent_name, content = await run_role(role, req)
        return agent_name, content, None
    except Exception as exc:
        logger.warning("Specialist role '%s' failed during execution", role, exc_info=True)
        try:
            profile = agent_catalog.get_profile(role) if agent_catalog is not None else None
            agent_name = profile.display_name if profile is not None else role
        except KeyError:
            agent_name = role
        return agent_name, "", str(exc)


async def run_parallel_roles(
    roles: tuple[str, ...],
    prompt_builder: Callable[[str], str],
    run_role: RoleRunner,
    state: DebateState,
    *,
    error_format: str = "[Fallo en {role}: {error}]",
    emit_message: bool = True,
    on_success: Callable[[str, str], None] | None = None,
    on_error: Callable[[str, str], None] | None = None,
    agent_catalog: IAgentCatalogRepository | None = None,
) -> AsyncGenerator[SupervisorEvent, None]:
    """Emit start events, execute roles concurrently, store outputs, and yield events."""
    for role in roles:
        yield SupervisorEvent(type=EventType.AGENT_STARTED, role=role, content="")

    results = await asyncio.gather(
        *(
            execute_role_safely(r, prompt_builder(r), run_role, agent_catalog=agent_catalog)
            for r in roles
        )
    )
    for role, content, error in results:
        if error:
            state.agent_outputs[role] = error_format.format(role=role, error=error)
            if on_error is not None:
                on_error(role, error)
            yield SupervisorEvent(
                type=EventType.ERROR,
                role=role,
                content=f"Error en {role}: {error}",
                metadata={"fatal": "false", "agent": role},
            )
            continue

        state.agent_outputs[role] = content
        if on_success is not None:
            on_success(role, content)
        if emit_message:
            yield SupervisorEvent(type=EventType.MESSAGE, role=role, content=content)
        yield SupervisorEvent(
            type=EventType.AGENT_COMPLETED,
            role=role,
            content=content,
            metadata=state.agent_metadata.get(role, {}),
        )


def determine_retry_targets(
    phase_roles: tuple[str, ...],
    state: DebateState,
    target_agents: list[str] | None = None,
) -> tuple[str, ...]:
    """Determine which roles to re-run on RETRY (explicit targets or failed roles)."""
    if target_agents:
        matched = tuple(r for r in phase_roles if r in target_agents)
        return matched if matched else tuple(target_agents)

    failed = tuple(
        r for r in phase_roles
        if FAILURE_MARKER in state.agent_outputs.get(r, "")
        or ERROR_MARKER in state.agent_outputs.get(r, "")
        or r not in state.agent_outputs
    )
    return failed or phase_roles


def apply_phase_hitl_decision(
    state: DebateState,
    hitl: HITLResponse,
    on_commit: Callable[[HITLResponse], None],
    *,
    apply_targets_before_early_exit: bool = True,
) -> tuple[bool, str]:
    """Apply HITL transition decisions uniformly and return ``(should_break, refinement)``."""
    if apply_targets_before_early_exit and hitl.target_agents:
        state.target_agents = hitl.target_agents

    if hitl.decision in (HITLDecision.FINISH, HITLDecision.CONSOLIDATE):
        state.finish_early = True
        state.skip_consolidation = hitl.decision == HITLDecision.FINISH
        on_commit(hitl)
        return True, ""

    if not apply_targets_before_early_exit and hitl.target_agents:
        state.target_agents = hitl.target_agents

    if hitl.decision in (HITLDecision.APPROVE, HITLDecision.DIVERT):
        if hitl.decision == HITLDecision.DIVERT and hitl.feedback:
            state.refinement = hitl.feedback
        on_commit(hitl)
        return True, ""

    if hitl.decision == HITLDecision.REFINE:
        state.refinement = hitl.feedback
        if not apply_targets_before_early_exit and hitl.target_agents:
            on_commit(hitl)
            return True, ""
        return bool(hitl.target_agents), hitl.feedback

    return False, ""


async def run_hitl_phase_loop(
    state: DebateState,
    phase_roles: tuple[str, ...],
    hitl_callback: HitlCallback,
    round_stream_factory: Callable[[tuple[str, ...], str], AsyncGenerator[SupervisorEvent, None]],
    hitl_decision_handler: Callable[[HITLResponse, str], tuple[bool, str]],
    *,
    error_markers: tuple[str, ...] = (FAILURE_MARKER, ERROR_MARKER),
    on_combined_content: Callable[[str], None] | None = None,
) -> AsyncGenerator[SupervisorEvent, None]:
    """
    Execute a repeating phase round + HITL checkpoint loop supporting RETRY, REFINE,
    APPROVE, DIVERT, CONSOLIDATE, and FINISH transitions.
    """
    refinement = ""
    roles_to_run = phase_roles
    lead_agent = phase_roles[0]

    while True:
        async for event in round_stream_factory(roles_to_run, refinement):
            yield event

        combined_content = SECTION_SEPARATOR.join(state.agent_outputs.get(r, "") for r in phase_roles)
        if on_combined_content is not None:
            on_combined_content(combined_content)

        has_error = any(
            any(marker in state.agent_outputs.get(r, "") for marker in error_markers)
            for r in phase_roles
        )
        hitl_metadata = {"checkpoint": f"after_{lead_agent}", "agent": lead_agent}
        if has_error:
            hitl_metadata["error_recovery"] = "true"

        hitl_event = SupervisorEvent(
            type=EventType.HITL_REQUIRED,
            role=lead_agent,
            content=combined_content,
            metadata=hitl_metadata,
        )
        yield hitl_event
        hitl = await hitl_callback(hitl_event)

        if hitl.decision == HITLDecision.RETRY:
            roles_to_run = determine_retry_targets(phase_roles, state, hitl.target_agents)
            continue

        should_break, refinement = hitl_decision_handler(hitl, combined_content)
        if should_break:
            break
        roles_to_run = phase_roles


def build_reviewer_prompt(
    reviewer_role: str,
    roles: tuple[str, ...],
    round_idx: int,
    state: DebateState,
) -> str:
    """Build domain-neutral critique prompt for a reviewer agent."""
    prior_critique_block = ""
    prior_critiques = state.get_agent_critiques(reviewer_role)
    if prior_critiques:
        prior_critique_block = (
            f"## Directivas previas emitidas por ti ({reviewer_role}) en la ronda anterior:\n"
            f"{prior_critiques[-1]}\n\n"
            f"⚠️ REGLA DE ORO DE COHERENCIA Y CONSISTENCIA:\n"
            f"- Evalúa si {', '.join(roles)} han aplicado las mejoras que tú mismo les indicaste en la ronda anterior.\n"
            f"- Si un agente ha solventado tu objeción (por ejemplo, eliminando un elemento innecesario o simplificando la propuesta), DEBES RECONOCERLO y NO CONTRADECIRTE pidiendo de vuelta lo que indicaste retirar.\n"
            f"- No muevas los objetivos ('moving the goalposts'). Céntrate únicamente en si las correcciones son válidas y en riesgos residuales reales proporcionados a la escala solicitada.\n\n"
        )

    proposals_block = "\n\n".join(
        f"## Propuesta de {r}\n{state.agent_outputs.get(r, '')}" for r in roles
    )

    return (
        f"Como {reviewer_role}, revisor imparcial y exigente:\n"
        f"Analiza de forma crítica y rigurosa las siguientes propuestas {'refinadas' if round_idx > 0 else 'preliminares'} de {', '.join(roles)} para resolver la necesidad planteada:\n\n"
        f"## Requisitos Formalizados\n{state.formalized}\n\n"
        f"{prior_critique_block}"
        f"{proposals_block}\n\n"
        f"Emite una crítica técnica constructiva pero exigente (máximo 250 palabras en total) indicando:\n"
        f"1. Si se han cumplido tus directivas previas (si aplica) y qué riesgos residuales persisten.\n"
        f"2. Puntos ciegos, riesgos, costes o limitaciones futuras proporcionados a la escala real solicitada.\n"
        f"3. Directivas de mejora concretas y consistentes con tus veredictos previos."
    )


async def run_review_rounds(
    state: DebateState,
    run_role: RoleRunner,
    roles: tuple[str, ...],
    reviewer_role: str,
    review_rounds: int,
    req: str,
) -> AsyncGenerator[SupervisorEvent, None]:
    """Run iterative critique + proposal refinement rounds for a single reviewer."""
    for round_idx in range(max(0, review_rounds)):
        yield SupervisorEvent(type=EventType.AGENT_STARTED, role=reviewer_role, content="")
        prompt = build_reviewer_prompt(reviewer_role, roles, round_idx, state)
        _, reviewer_critique, rev_error = await execute_role_safely(reviewer_role, prompt, run_role)
        if rev_error:
            yield SupervisorEvent(
                type=EventType.ERROR,
                role=reviewer_role,
                content=f"Error en {reviewer_role}: {rev_error}",
                metadata={"fatal": "false", "agent": reviewer_role},
            )
            reviewer_critique = f"[Crítica no disponible debido a error: {rev_error}]"
        else:
            state.add_agent_critique(reviewer_role, reviewer_critique)
            state.agent_outputs[reviewer_role] = reviewer_critique
            yield SupervisorEvent(
                type=EventType.AGENT_COMPLETED,
                role=reviewer_role,
                content=reviewer_critique,
                metadata=state.agent_metadata.get(reviewer_role, {}),
            )

        def _build_refine_prompt(role_name: str, critique: str = reviewer_critique) -> str:
            current_proposal = state.agent_outputs.get(role_name, "")
            return (
                f"{req}\n\n"
                f"## Tu propuesta previa\n{current_proposal}\n\n"
                f"## Crítica y objeciones técnicas de {reviewer_role}\n{critique}\n\n"
                f"Refina y robustece tus propuestas, respondiendo y solventando las observaciones y riesgos identificados por {reviewer_role} (mediante mitigaciones técnicas, aislamiento de fallos o justificación de trade-offs), manteniendo firme tu identidad y enfoque de diseño diferencial sin claudicar en tu visión innovadora o pragmática antes del arbitraje humano."
            )

        async for event in run_parallel_roles(
            roles,
            _build_refine_prompt,
            run_role,
            state,
            error_format="[Fallo al refinar propuesta de {role}: {error}]",
            emit_message=True,
        ):
            yield event


def build_phase_3_prompt(state: DebateState, agent_name: str, refinement: str) -> str:
    """Build evaluation prompt incorporating selected proposals and coherence directives."""
    if state.selected_solutions:
        proposals_text = (
            "The user has selected the following options to review:\n"
            + ", ".join(state.selected_solutions)
            + "\n\nRefer to the proposals above and ONLY critique the selected ones."
        )
    else:
        proposals_text = "Review the following proposals:\n\n" + state.hitl2_content

    critiques_context = ""
    prior_critiques = state.get_agent_critiques(agent_name)
    if prior_critiques:
        critiques_context = (
            f"\n\n## Directivas y críticas emitidas previamente por ti ({agent_name}) durante este debate:\n"
            + "\n---\n".join(prior_critiques)
            + "\n\n⚠️ REGLA DE COHERENCIA EVALUATIVA:\n"
            "Sé plenamente coherente y consecuente con tus directivas previas. "
            "Si los agentes proponentes ya corrigieron tus objeciones (por ejemplo, eliminando elementos innecesarios o simplificando la solución), "
            "valida esa corrección positivamente. ESTÁ TERMINANTEMENTE PROHIBIDO contradecirte exigiendo ahora lo opuesto a lo que ordenaste retirar."
        )

    user_refinement_context = f"\n\n## User Refinement\n{refinement}" if refinement else ""
    return state.formalized + "\n\n" + proposals_text + critiques_context + user_refinement_context


async def execute_phase_1_interpreters(
    state: DebateState,
    user_request: str,
    run_role: RoleRunner,
    hitl_callback: HitlCallback,
    interpreter_roles: tuple[str, ...],
) -> AsyncGenerator[SupervisorEvent, None]:
    """Phase 1: formalize requirements and coordinate HITL checkpoint 1."""
    if not interpreter_roles:
        state.formalized = user_request
        return

    def _round_stream(roles_to_run: tuple[str, ...], refinement: str) -> AsyncGenerator[SupervisorEvent, None]:
        req = user_request + (f"\n\n## User Refinement\n{refinement}" if refinement else "")
        return run_parallel_roles(
            roles_to_run,
            constant_prompt(req),
            run_role,
            state,
            error_format="[Error en {role}: {error}]",
        )

    def _on_hitl(hitl: HITLResponse, _combined: str) -> tuple[bool, str]:
        successful_outputs = [
            state.agent_outputs.get(a, "")
            for a in interpreter_roles
            if not (ERROR_MARKER in state.agent_outputs.get(a, "") or FAILURE_MARKER in state.agent_outputs.get(a, ""))
        ]
        effective_formalized = SECTION_SEPARATOR.join(successful_outputs) if successful_outputs else user_request

        def _commit(_resp: HITLResponse) -> None:
            state.formalized = effective_formalized

        return apply_phase_hitl_decision(
            state,
            hitl,
            _commit,
            apply_targets_before_early_exit=False,
        )

    async for event in run_hitl_phase_loop(
        state,
        interpreter_roles,
        hitl_callback,
        _round_stream,
        _on_hitl,
        error_markers=(ERROR_MARKER,),
    ):
        yield event


async def _execute_proposer_round(
    state: DebateState,
    run_role: RoleRunner,
    roles_to_run: tuple[str, ...],
    reviewer_roles: tuple[str, ...],
    review_rounds: int,
    refinement: str,
) -> AsyncGenerator[SupervisorEvent, None]:
    req = state.formalized + (f"\n\n## User Refinement\n{refinement}" if refinement else "")
    has_reviews = bool(reviewer_roles and review_rounds > 0)
    async for event in run_parallel_roles(
        roles_to_run,
        constant_prompt(req),
        run_role,
        state,
        error_format="[Fallo al generar propuesta de {role}: {error}]",
        emit_message=not has_reviews,
    ):
        yield event

    if not reviewer_roles or review_rounds <= 0:
        return
    for reviewer_role in reviewer_roles:
        async for event in run_review_rounds(state, run_role, roles_to_run, reviewer_role, review_rounds, req):
            yield event


async def execute_phase_2_proposers(
    state: DebateState,
    run_role: RoleRunner,
    hitl_callback: HitlCallback,
    proposer_roles: tuple[str, ...],
    reviewer_roles: tuple[str, ...],
    review_rounds: int = 1,
) -> AsyncGenerator[SupervisorEvent, None]:
    """Phase 2: generate competing proposals, iterate reviews, and coordinate HITL checkpoint 2."""
    if not proposer_roles:
        return

    def _round_stream(roles_to_run: tuple[str, ...], refinement: str) -> AsyncGenerator[SupervisorEvent, None]:
        return _execute_proposer_round(
            state,
            run_role,
            roles_to_run,
            reviewer_roles,
            review_rounds,
            refinement,
        )

    def _store_hitl2(combined: str) -> None:
        state.hitl2_content = combined

    def _on_hitl(hitl: HITLResponse, _combined: str) -> tuple[bool, str]:
        def _commit(resp: HITLResponse) -> None:
            state.selected_solutions = resp.selected_options

        return apply_phase_hitl_decision(state, hitl, _commit, apply_targets_before_early_exit=True)

    async for event in run_hitl_phase_loop(
        state,
        proposer_roles,
        hitl_callback,
        _round_stream,
        _on_hitl,
        on_combined_content=_store_hitl2,
    ):
        yield event


async def execute_phase_3_evaluators(
    state: DebateState,
    run_role: RoleRunner,
    hitl_callback: HitlCallback,
    evaluator_roles: tuple[str, ...],
) -> AsyncGenerator[SupervisorEvent, None]:
    """Phase 3: evaluate selected proposals and coordinate HITL checkpoint 3."""
    if not evaluator_roles:
        return

    def _round_stream(roles_to_run: tuple[str, ...], refinement: str) -> AsyncGenerator[SupervisorEvent, None]:
        def _prompt(agent_name: str) -> str:
            return build_phase_3_prompt(state, agent_name, refinement)

        return run_parallel_roles(
            roles_to_run,
            _prompt,
            run_role,
            state,
            error_format="[Fallo en evaluación de {role}: {error}]",
            on_success=lambda role, verdict: state.add_agent_critique(role, verdict),
            on_error=lambda role, err: state.add_agent_critique(role, f"Error: {err}"),
        )

    def _on_hitl(hitl: HITLResponse, _combined: str) -> tuple[bool, str]:
        def _commit(resp: HITLResponse) -> None:
            state.final_solutions = resp.selected_options or state.selected_solutions

        return apply_phase_hitl_decision(state, hitl, _commit, apply_targets_before_early_exit=True)

    async for event in run_hitl_phase_loop(
        state,
        evaluator_roles,
        hitl_callback,
        _round_stream,
        _on_hitl,
        error_markers=(FAILURE_MARKER,),
    ):
        yield event


async def execute_phase_4_implementers(
    state: DebateState,
    run_role: RoleRunner,
    implementer_roles: tuple[str, ...],
) -> AsyncGenerator[SupervisorEvent, None]:
    """Phase 4: run implementer agents in parallel on the approved solution."""
    if not implementer_roles:
        return

    impl_context = (
        "Selected Final Solutions:\n" + ", ".join(state.final_solutions)
        if state.final_solutions
        else state.hitl2_content
    )
    req = state.formalized + "\n\n" + impl_context

    async for event in run_parallel_roles(
        implementer_roles,
        constant_prompt(req),
        run_role,
        state,
        error_format="[Fallo en {role}: {error}]",
        emit_message=True,
    ):
        yield event

