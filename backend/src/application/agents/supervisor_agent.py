"""
Application Agent: SupervisorAgent

Orchestrates a multi-agent debate through a typed async event stream.
Returns an AsyncGenerator[SupervisorEvent, None] — compatible with WebSocket
streaming (ADR-016) and iteration in tests.

This module does NOT know which agents take part in the debate. They are resolved
through the declarative topology (topology.yaml) and the agent registry
(agents.yaml), so adding, removing or renaming agents never requires touching it.

Debate flow, expressed in the functional slots of ``DebateTopology``:
  Triage (supervisor):
    direct chat | single specialist | adaptive debate (with or without interpreter)

  Phase 1 (interpreter):
    formalizes the user request → HITL ①

  Phase 2 (proposers + reviewer):
    proposers work in parallel, the reviewer critiques them for ``review_rounds``
    iterations → HITL ②

  Phase 3 (evaluator):
    issues a verdict on the selected proposals → HITL ③

  Phase 4 (implementers):
    work in parallel on the approved solution

  Consolidation (supervisor):
    final LLM call aggregating all agent outputs → DONE event

ADR-016: Converted to async generator for native WebSocket integration.
ADR-015: No ADK dependency. hitl_callback is now an async callable.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any
from collections.abc import AsyncGenerator, Awaitable, Callable

from src.application.agents.sub_agent_runner import SubAgentRunner
from src.domain.agents.debate_topology import DebateTopology, load_topology
from src.domain.agents.sub_agent_profiles import get_all_profiles, get_profile
from src.domain.agents.supervisor_events import (
    EventType,
    HITLDecision,
    HITLResponse,
    SupervisorEvent,
)
from src.domain.ports.document_store import IDocumentStore
from src.domain.ports.llm_provider import ILLMProvider

import json
import re
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Prompt template for final consolidation (in Spanish, authoritative)
# ---------------------------------------------------------------------------
_CONSOLIDATION_PROMPT = """\
Eres {supervisor_name}, la autoridad máxima y orquestadora del consejo de agentes.
El consejo colegiado de especialistas ha concluido su deliberación.
Genera un documento estructurado en Markdown (300-500 palabras) que consolide todas las perspectivas en un dictamen claro, vinculante y de nivel de producción.

Estructura obligatoria en español:
## 1. Resumen Ejecutivo y Dictamen Estratégico
El enfoque final adoptado y la justificación de la decisión colegiada.

## 2. Decisiones y Enfoques Clave
Síntesis de las propuestas de los agentes proponentes ({proposers_str}), equilibrando sus distintas visiones.

## 3. Mitigación de Riesgos y Evaluación Crítica
Cómo se resuelven de forma concreta y accionable las vulnerabilidades, advertencias y directivas identificadas por el agente evaluador ({evaluator_name}).

## 4. Directivas de Implementación
Criterios y pasos operativos acordes a las aportaciones de los agentes de implementación ({implementers_str}).

## 5. Plan de Acción Inmediato
Pasos concretos y numerados para el equipo.

--- Aportaciones del Consejo ---
{debate_context}
"""


@dataclass(frozen=True)
class TriageDecision:
    mode: str  # "direct_chat" | "single_agent" | "adaptive_debate"
    target_agent: str | None = None
    skip_interpreter: bool = False
    reasoning: str = ""


def _parse_triage_json(raw: str) -> dict[str, Any] | None:
    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return json.loads(raw)
    except Exception:
        return None


def classify_intent(
    user_request: str,
    llm_provider: ILLMProvider,
    model_name: str,
    supervisor_name: str,
    interpreter_name: str,
) -> TriageDecision:
    req_clean = user_request.strip().lower()

    # Fast heuristics for direct greetings or direct questions to the supervisor
    greetings = (r"^hola\b", r"^buenos d[ií]as\b", r"^buenas tardes\b", r"^buenas noches\b", r"^qui[eé]n eres\b", r"^qu[eé] haces\b", r"^c[oó]mo est[aá]s\b")
    for g in greetings:
        if re.search(g, req_clean):
            return TriageDecision(mode="direct_chat", reasoning=f"Saludo o consulta directa a {supervisor_name}")

    # Single-agent targets: every registered agent except the supervisor and the interpreter
    specialists = [
        p for p in get_all_profiles()
        if not p.is_supervisor and p.display_name.lower() != interpreter_name.lower() and p.id != interpreter_name
    ]
    specialists_lines = "\n".join(
        f'   - "{p.display_name}" ({p.id}): {p.description}'
        for p in specialists
    )
    specialist_names_union = " | ".join(f'"{p.display_name}"' for p in specialists) + " | null"

    triage_prompt = f"""\
Eres {supervisor_name}. Analiza la petición del usuario y clasifica la intención para determinar la estrategia de ejecución óptima del consejo de agentes:

1. "direct_chat": Saludos, preguntas directas a {supervisor_name} sobre quién es o su consejo, dudas conceptuales rápidas o reflexiones donde NO se requiere un trabajo técnico ni un debate.
2. "single_agent": El usuario solicita expresamente una tarea acotada a un único especialista:
{specialists_lines}
3. "adaptive_debate": Problemas o requerimientos que necesitan deliberación colegiada del consejo.
   - skip_interpreter=false: La petición es vaga, coloquial o requiere desambiguación y formalización de requisitos por parte de {interpreter_name}.
   - skip_interpreter=true: La petición ya incluye requisitos estrictos, métricas, componentes y restricciones bien definidas.

Responde ÚNICAMENTE un objeto JSON válido con este formato:
{{
  "mode": "direct_chat" | "single_agent" | "adaptive_debate",
  "target_agent": {specialist_names_union},
  "skip_interpreter": true | false,
  "reasoning": "Breve justificación de 1 frase"
}}

Petición del usuario:
{user_request}
"""
    try:
        raw_res = llm_provider.complete(triage_prompt, model_name)
        parsed = _parse_triage_json(raw_res)
        if parsed and isinstance(parsed, dict) and "mode" in parsed:
            mode = parsed.get("mode", "adaptive_debate")
            target_str = parsed.get("target_agent")
            target_agent = None
            if target_str:
                try:
                    p = get_profile(target_str)
                    target_agent = p.display_name
                except KeyError:
                    target_agent = str(target_str)
            skip_interpreter = bool(parsed.get("skip_interpreter", False))
            reasoning = str(parsed.get("reasoning", ""))
            return TriageDecision(mode=mode, target_agent=target_agent, skip_interpreter=skip_interpreter, reasoning=reasoning)
    except Exception:
        pass

    return TriageDecision(mode="adaptive_debate", target_agent=None, skip_interpreter=False, reasoning="Fallback estándar")


class SupervisorAgent:
    """Stateless async orchestrator for the multi-agent debate."""

    @staticmethod
    def run(
        user_request: str,
        document_store: IDocumentStore,
        agent_config_repo: Any,
        llm_factory: Callable[[str], ILLMProvider],
        hitl_callback: Callable[[SupervisorEvent], Awaitable[HITLResponse]],
        chat_history: list[dict[str, Any]] | None = None,
        review_rounds: int | None = None,
        topology: DebateTopology | None = None,
    ) -> AsyncGenerator[SupervisorEvent, None]:
        """
        Run the full debate flow and yield SupervisorEvents asynchronously (ADR-016).
        """
        return _debate_generator(
            user_request=user_request,
            document_store=document_store,
            agent_config_repo=agent_config_repo,
            llm_factory=llm_factory,
            hitl_callback=hitl_callback,
            chat_history=chat_history,
            review_rounds=review_rounds,
            topology=topology,
        )


class DebateState:
    """Mutable state of one debate. Agent-agnostic: everything is keyed by agent name."""

    def __init__(self) -> None:
        self.agent_outputs: dict[str, str] = {}
        self.agent_metadata: dict[str, dict[str, str]] = {}
        self.formalized: str = ""
        self.selected_solutions: list[str] = []
        self.final_solutions: list[str] = []
        self.hitl2_content: str = ""
        self.target_agents: list[str] = []
        self.refinement: str = ""
        self.agent_critiques: dict[str, list[str]] = {}
        self.debate_history: list[dict[str, Any]] = []

    def get_agent_critiques(self, agent_name: str) -> list[str]:
        return self.agent_critiques.get(agent_name, [])

    def add_agent_critique(self, agent_name: str, critique: str) -> None:
        self.agent_critiques.setdefault(agent_name, []).append(critique)


def _determine_review_rounds(
    review_rounds: int | None,
    topology: DebateTopology | None,
    active_topology: DebateTopology,
    settings: Any,
) -> int:
    if review_rounds is not None:
        return review_rounds
    if topology is not None and topology.review_rounds is not None:
        return topology.review_rounds
    if settings.review_rounds is not None:
        return settings.review_rounds
    if active_topology.review_rounds is not None:
        return active_topology.review_rounds
    return 1


def _resolve_supervisor_config(
    agent_config_repo: Any,
    profile: Any,
    settings: Any,
) -> tuple[str, str]:
    config = agent_config_repo.find_by_role(profile.display_name) or agent_config_repo.find_by_role(profile.id)
    provider_name = config.provider if config else settings.default_provider
    model_name = config.model_name if config else settings.default_model
    return provider_name, model_name


async def _run_direct_chat_mode(
    user_request: str,
    chat_history: list[dict[str, Any]] | None,
    supervisor_profile: Any,
    supervisor_provider: Any,
    sup_agent_name: str,
    sup_model_name: str,
) -> AsyncGenerator[SupervisorEvent, None]:
    yield SupervisorEvent(type=EventType.AGENT_STARTED, role=sup_agent_name, content="")

    hist_lines = []
    if chat_history:
        for m in chat_history:
            hist_lines.append(f"- {m.get('role', 'user')}: {m.get('content', '')}")
    hist_str = "\n".join(hist_lines)

    direct_prompt = f"""# INSTRUCCIÓN DE SISTEMA
{supervisor_profile.system_prompt}

# HISTORIAL DE CONVERSACIÓN
{hist_str or 'Sin historial previo.'}

# MENSAJE DEL USUARIO
{user_request}

Responde directamente al usuario como {sup_agent_name} en español, manteniendo la personalidad y el tono definidos en tu instrucción de sistema."""
    start_time = time.perf_counter()
    resp_text = await asyncio.to_thread(supervisor_provider.complete, direct_prompt, sup_model_name)
    latency = round(time.perf_counter() - start_time, 2)
    meta = {
        "model": sup_model_name,
        "latency_seconds": str(latency),
        "tokens": str(max(1, len(resp_text) // 4)),
    }
    yield SupervisorEvent(type=EventType.AGENT_COMPLETED, role=sup_agent_name, content=resp_text, metadata=meta)
    yield SupervisorEvent(type=EventType.DONE, role=sup_agent_name, content=resp_text, metadata=meta)


async def _run_single_agent_mode(
    target_agent: str,
    user_request: str,
    run_role: Callable[[str, str], Awaitable[tuple[str, str]]],
    state: DebateState,
) -> AsyncGenerator[SupervisorEvent, None]:
    target_name = get_profile(target_agent).display_name
    yield SupervisorEvent(type=EventType.AGENT_STARTED, role=target_name, content="")
    _, content = await run_role(target_name, user_request)
    meta = state.agent_metadata.get(target_name, {})
    yield SupervisorEvent(type=EventType.AGENT_COMPLETED, role=target_name, content=content, metadata=meta)
    yield SupervisorEvent(type=EventType.DONE, role=target_name, content=content, metadata=meta)


def _resolve_target_agents(agent_names: list[str]) -> list[str]:
    resolved = []
    for a in agent_names:
        try:
            p = get_profile(a)
            resolved.append(p.display_name)
        except KeyError:
            resolved.append(a)
    return resolved


async def _execute_target_agents(
    agent_names: list[str],
    base_req: str,
    refinement: str,
    run_role: Callable[[str, str], Awaitable[tuple[str, str]]],
    state: DebateState,
) -> AsyncGenerator[SupervisorEvent, None]:
    for a in agent_names:
        yield SupervisorEvent(type=EventType.AGENT_STARTED, role=a, content="")
    req = base_req + (f"\n\n## User Refinement\n{refinement}" if refinement else "")
    results = await asyncio.gather(*(run_role(a, req) for a in agent_names))
    for a, content in results:
        state.agent_outputs[a] = content
        yield SupervisorEvent(
            type=EventType.AGENT_COMPLETED,
            role=a,
            content=content,
            metadata=state.agent_metadata.get(a, {}),
        )


async def _maybe_divert_to_targets(
    state: DebateState,
    run_role: Callable[[str, str], Awaitable[tuple[str, str]]],
    supervisor_provider: Any,
    sup_model_name: str,
    sup_agent_name: str,
    active_topology: DebateTopology,
) -> AsyncGenerator[SupervisorEvent, None]:
    target_agents = _resolve_target_agents(state.target_agents)
    if not target_agents:
        return
    async for event in _execute_target_agents(target_agents, state.formalized, state.refinement, run_role, state):
        yield event
    yield await _run_consolidation(
        state,
        supervisor_provider,
        sup_model_name,
        supervisor_name=sup_agent_name,
        topology=active_topology,
    )


def _build_role_runner(
    agent_config_repo: Any,
    document_store: IDocumentStore,
    llm_factory: Callable[[str], ILLMProvider],
    settings: Any,
    chat_history: list[dict[str, Any]] | None,
    state: DebateState,
) -> Callable[[str, str], Awaitable[tuple[str, str]]]:
    async def run_role(r: str, req: str) -> tuple[str, str]:
        profile = get_profile(r)
        agent_name = profile.display_name

        config = agent_config_repo.find_by_role(agent_name) or agent_config_repo.find_by_role(profile.id)
        provider_name = config.provider if config else settings.default_provider
        model_name = config.model_name if config else settings.default_model

        llm_provider = llm_factory(provider_name)
        runner_kwargs = {"chat_history": chat_history} if chat_history else {}
        resp = await SubAgentRunner.run(
            role=agent_name,
            user_request=req,
            llm_provider=llm_provider,
            document_store=document_store,
            model_name=model_name,
            **runner_kwargs,
        )
        meta = {
            "model": resp.model_name or model_name,
            "prompt_tokens": str(resp.tokens.get("input", 0)),
            "completion_tokens": str(resp.tokens.get("output", 0)),
            "total_tokens": str(resp.tokens.get("total", 0)),
            "latency_seconds": str(resp.latency),
            "tokens": str(resp.tokens.get("total", 0)),
        }
        state.agent_metadata[agent_name] = meta
        state.agent_metadata[profile.id] = meta
        state.agent_outputs[profile.id] = resp.content
        state.agent_outputs[agent_name] = resp.content
        state.debate_history.append({"role": "assistant", "name": agent_name, "content": resp.content})
        return agent_name, resp.content

    return run_role


async def _run_phase_with_divert(
    phase_gen: AsyncGenerator[SupervisorEvent, None],
    state: DebateState,
    run_role: Callable[[str, str], Awaitable[tuple[str, str]]],
    supervisor_provider: Any,
    sup_model_name: str,
    sup_agent_name: str,
    active_topology: DebateTopology,
) -> AsyncGenerator[SupervisorEvent, None]:
    async for event in phase_gen:
        yield event
    if state.target_agents:
        async for event in _maybe_divert_to_targets(
            state, run_role, supervisor_provider, sup_model_name, sup_agent_name, active_topology
        ):
            yield event


async def _execute_phase_1_if_needed(
    state: DebateState,
    user_request: str,
    run_role: Callable[[str, str], Awaitable[tuple[str, str]]],
    hitl_callback: Callable[[SupervisorEvent], Awaitable[HITLResponse]],
    triage: Any,
    interpreter_role: str,
) -> AsyncGenerator[SupervisorEvent, None]:
    if not triage.skip_interpreter:
        async for event in _run_phase_1(
            state,
            user_request,
            run_role,
            hitl_callback,
            interpreter_role=interpreter_role,
        ):
            yield event
    else:
        state.formalized = user_request


async def _run_adaptive_debate(
    state: DebateState,
    user_request: str,
    run_role: Callable[[str, str], Awaitable[tuple[str, str]]],
    hitl_callback: Callable[[SupervisorEvent], Awaitable[HITLResponse]],
    triage: Any,
    active_topology: DebateTopology,
    effective_review_rounds: int,
    supervisor_provider: Any,
    sup_model_name: str,
    sup_agent_name: str,
) -> AsyncGenerator[SupervisorEvent, None]:
    phase1 = _execute_phase_1_if_needed(
        state, user_request, run_role, hitl_callback, triage, active_topology.interpreter
    )
    async for event in _run_phase_with_divert(
        phase1, state, run_role, supervisor_provider, sup_model_name, sup_agent_name, active_topology
    ):
        yield event
    if state.target_agents:
        return

    phase2 = _run_phase_2(
        state,
        run_role,
        hitl_callback,
        review_rounds=effective_review_rounds,
        proposer_roles=active_topology.proposers,
        reviewer_role=active_topology.reviewer,
    )
    async for event in _run_phase_with_divert(
        phase2, state, run_role, supervisor_provider, sup_model_name, sup_agent_name, active_topology
    ):
        yield event
    if state.target_agents:
        return

    phase3 = _run_phase_3(
        state,
        run_role,
        hitl_callback,
        evaluator_role=active_topology.evaluator,
    )
    async for event in _run_phase_with_divert(
        phase3, state, run_role, supervisor_provider, sup_model_name, sup_agent_name, active_topology
    ):
        yield event
    if state.target_agents:
        return

    async for event in _run_phase_4(
        state,
        run_role,
        implementer_roles=active_topology.implementers,
    ):
        yield event

    yield await _run_consolidation(
        state, supervisor_provider, sup_model_name, supervisor_name=sup_agent_name, topology=active_topology
    )


async def _debate_generator(
    user_request: str,
    document_store: IDocumentStore,
    agent_config_repo: Any,
    llm_factory: Callable[[str], ILLMProvider],
    hitl_callback: Callable[[SupervisorEvent], Awaitable[HITLResponse]],
    chat_history: list[dict[str, Any]] | None = None,
    review_rounds: int | None = None,
    topology: DebateTopology | None = None,
) -> AsyncGenerator[SupervisorEvent, None]:
    from src.presentation.api.config import get_settings
    settings = get_settings()

    active_topology = topology or load_topology()
    effective_review_rounds = _determine_review_rounds(review_rounds, topology, active_topology, settings)
    state = DebateState()

    supervisor_profile = get_profile(active_topology.supervisor)
    sup_agent_name = supervisor_profile.display_name
    sup_provider_name, sup_model_name = _resolve_supervisor_config(agent_config_repo, supervisor_profile, settings)
    supervisor_provider = llm_factory(sup_provider_name)

    run_role = _build_role_runner(
        agent_config_repo, document_store, llm_factory, settings, chat_history, state
    )

    # 1. Triage Intent Classification
    interpreter_profile = get_profile(active_topology.interpreter)
    triage = classify_intent(
        user_request,
        supervisor_provider,
        sup_model_name,
        supervisor_name=sup_agent_name,
        interpreter_name=interpreter_profile.display_name,
    )

    # 2. Direct Chat Mode (Supervisor responds without council)
    if triage.mode == "direct_chat":
        async for event in _run_direct_chat_mode(
            user_request, chat_history, supervisor_profile, supervisor_provider, sup_agent_name, sup_model_name
        ):
            yield event
        return

    # 3. Single Agent Mode (direct delegation to specialist)
    if triage.mode == "single_agent" and triage.target_agent:
        async for event in _run_single_agent_mode(triage.target_agent, user_request, run_role, state):
            yield event
        return

    # 4. Adaptive Debate Mode
    async for event in _run_adaptive_debate(
        state,
        user_request,
        run_role,
        hitl_callback,
        triage,
        active_topology,
        effective_review_rounds,
        supervisor_provider,
        sup_model_name,
        sup_agent_name,
    ):
        yield event



async def _run_phase_1(
    state: DebateState,
    user_request: str,
    run_role: Callable[[str, str], Awaitable[tuple[str, str]]],
    hitl_callback: Callable[[SupervisorEvent], Awaitable[HITLResponse]],
    interpreter_role: str,
) -> AsyncGenerator[SupervisorEvent, None]:
    refinement = ""
    agent_name = interpreter_role
    while True:
        req = user_request + (f"\n\n## User Refinement\n{refinement}" if refinement else "")
        yield SupervisorEvent(type=EventType.AGENT_STARTED, role=agent_name, content="")
        _, nl_content = await run_role(agent_name, req)
        state.agent_outputs[agent_name] = nl_content
        yield SupervisorEvent(
            type=EventType.AGENT_COMPLETED,
            role=agent_name,
            content=nl_content,
            metadata=state.agent_metadata.get(agent_name, {}),
        )
        
        hitl_event = SupervisorEvent(
            type=EventType.HITL_REQUIRED,
            role=agent_name,
            content=nl_content,
            metadata={"checkpoint": f"after_{agent_name}", "agent": agent_name},
        )
        yield hitl_event
        hitl = await hitl_callback(hitl_event)

        if hitl.target_agents:
            state.target_agents = hitl.target_agents

        if hitl.decision == HITLDecision.APPROVE:
            state.formalized = nl_content
            break
        elif hitl.decision == HITLDecision.REFINE:
            refinement = hitl.feedback
            state.refinement = refinement
            if hitl.target_agents:
                state.formalized = nl_content
                break


async def _run_proposers_round(
    roles: tuple[str, ...],
    req: str,
    run_role: Callable[[str, str], Awaitable[tuple[str, str]]],
    state: DebateState,
) -> AsyncGenerator[SupervisorEvent, None]:
    for role in roles:
        yield SupervisorEvent(type=EventType.AGENT_STARTED, role=role, content="")

    results = await asyncio.gather(*(run_role(r, req) for r in roles))
    for role, content in results:
        state.agent_outputs[role] = content
        yield SupervisorEvent(
            type=EventType.AGENT_COMPLETED,
            role=role,
            content=content,
            metadata=state.agent_metadata.get(role, {}),
        )


def _build_reviewer_prompt(
    reviewer_role: str,
    roles: tuple[str, ...],
    round_idx: int,
    state: DebateState,
) -> str:
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


async def _run_review_rounds(
    state: DebateState,
    run_role: Callable[[str, str], Awaitable[tuple[str, str]]],
    roles: tuple[str, ...],
    reviewer_role: str,
    review_rounds: int,
    req: str,
) -> AsyncGenerator[SupervisorEvent, None]:
    for round_idx in range(max(0, review_rounds)):
        yield SupervisorEvent(type=EventType.AGENT_STARTED, role=reviewer_role, content="")
        prompt = _build_reviewer_prompt(reviewer_role, roles, round_idx, state)
        _, reviewer_critique = await run_role(reviewer_role, prompt)
        state.add_agent_critique(reviewer_role, reviewer_critique)
        yield SupervisorEvent(
            type=EventType.AGENT_COMPLETED,
            role=reviewer_role,
            content=reviewer_critique,
            metadata=state.agent_metadata.get(reviewer_role, {}),
        )

        for role in roles:
            yield SupervisorEvent(type=EventType.AGENT_STARTED, role=role, content="")

        def _build_refine_prompt(role_name: str) -> str:
            current_proposal = state.agent_outputs.get(role_name, "")
            return (
                f"{req}\n\n"
                f"## Tu propuesta previa\n{current_proposal}\n\n"
                f"## Crítica y objeciones técnicas de {reviewer_role}\n{reviewer_critique}\n\n"
                f"Refina y robustece tus propuestas, solventando las observaciones y riesgos identificados por {reviewer_role} y asegurando su viabilidad futura y solidez operativa."
            )

        results_refine = await asyncio.gather(
            *(run_role(r, _build_refine_prompt(r)) for r in roles)
        )

        for role, content in results_refine:
            state.agent_outputs[role] = content
            yield SupervisorEvent(
                type=EventType.AGENT_COMPLETED,
                role=role,
                content=content,
                metadata=state.agent_metadata.get(role, {}),
            )


def _process_phase_2_hitl(state: DebateState, hitl: HITLResponse) -> tuple[bool, str]:
    if hitl.target_agents:
        state.target_agents = hitl.target_agents

    if hitl.decision == HITLDecision.APPROVE:
        state.selected_solutions = hitl.selected_options
        return True, ""
    if hitl.decision == HITLDecision.REFINE:
        state.refinement = hitl.feedback
        return (True if hitl.target_agents else False), hitl.feedback
    return False, ""


async def _run_phase_2(
    state: DebateState,
    run_role: Callable[[str, str], Awaitable[tuple[str, str]]],
    hitl_callback: Callable[[SupervisorEvent], Awaitable[HITLResponse]],
    proposer_roles: tuple[str, ...],
    reviewer_role: str,
    review_rounds: int = 1,
) -> AsyncGenerator[SupervisorEvent, None]:
    refinement = ""
    roles = proposer_roles
    lead_agent = roles[0] if roles else "proposers"
    while True:
        req = state.formalized + (f"\n\n## User Refinement\n{refinement}" if refinement else "")
        async for event in _run_proposers_round(roles, req, run_role, state):
            yield event

        async for event in _run_review_rounds(state, run_role, roles, reviewer_role, review_rounds, req):
            yield event

        state.hitl2_content = "\n\n---\n\n".join(state.agent_outputs.get(r, "") for r in roles)
        hitl_event = SupervisorEvent(
            type=EventType.HITL_REQUIRED,
            role=lead_agent,
            content=state.hitl2_content,
            metadata={"checkpoint": f"after_{lead_agent}", "agent": lead_agent},
        )
        yield hitl_event
        hitl = await hitl_callback(hitl_event)

        should_break, refinement = _process_phase_2_hitl(state, hitl)
        if should_break:
            break


def _build_phase_3_prompt(state: DebateState, agent_name: str, refinement: str) -> str:
    if state.selected_solutions:
        proposals_text = "The user has selected the following options to review:\n" + ", ".join(state.selected_solutions)
        proposals_text += "\n\nRefer to the proposals above and ONLY critique the selected ones."
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


def _process_phase_3_hitl(state: DebateState, hitl: HITLResponse) -> tuple[bool, str]:
    if hitl.target_agents:
        state.target_agents = hitl.target_agents

    if hitl.decision == HITLDecision.APPROVE:
        state.final_solutions = hitl.selected_options or state.selected_solutions
        return True, ""
    if hitl.decision == HITLDecision.REFINE:
        state.refinement = hitl.feedback
        return (True if hitl.target_agents else False), hitl.feedback
    return False, ""


async def _run_phase_3(
    state: DebateState,
    run_role: Callable[[str, str], Awaitable[tuple[str, str]]],
    hitl_callback: Callable[[SupervisorEvent], Awaitable[HITLResponse]],
    evaluator_role: str,
) -> AsyncGenerator[SupervisorEvent, None]:
    refinement = ""
    agent_name = evaluator_role

    while True:
        req = _build_phase_3_prompt(state, agent_name, refinement)
        yield SupervisorEvent(type=EventType.AGENT_STARTED, role=agent_name, content="")
        _, verdict = await run_role(agent_name, req)
        state.agent_outputs[agent_name] = verdict
        state.add_agent_critique(agent_name, verdict)
        yield SupervisorEvent(
            type=EventType.AGENT_COMPLETED,
            role=agent_name,
            content=verdict,
            metadata=state.agent_metadata.get(agent_name, {}),
        )

        hitl_event = SupervisorEvent(
            type=EventType.HITL_REQUIRED,
            role=agent_name,
            content=verdict,
            metadata={"checkpoint": f"after_{agent_name}", "agent": agent_name},
        )
        yield hitl_event
        hitl = await hitl_callback(hitl_event)

        should_break, refinement = _process_phase_3_hitl(state, hitl)
        if should_break:
            break


async def _run_phase_4(
    state: DebateState,
    run_role: Callable[[str, str], Awaitable[tuple[str, str]]],
    implementer_roles: tuple[str, ...],
) -> AsyncGenerator[SupervisorEvent, None]:
    impl_context = "Selected Final Solutions:\n" + ", ".join(state.final_solutions) if state.final_solutions else state.hitl2_content
    req = state.formalized + "\n\n" + impl_context
    
    roles_impl = implementer_roles
    for role in roles_impl:
        yield SupervisorEvent(type=EventType.AGENT_STARTED, role=role, content="")
        
    results_impl = await asyncio.gather(*(run_role(r, req) for r in roles_impl))
    
    for role, content in results_impl:
        state.agent_outputs[role] = content
        yield SupervisorEvent(
            type=EventType.AGENT_COMPLETED,
            role=role,
            content=content,
            metadata=state.agent_metadata.get(role, {}),
        )


async def _run_consolidation(
    state: DebateState,
    default_provider: ILLMProvider,
    default_model: str,
    supervisor_name: str,
    topology: DebateTopology,
) -> SupervisorEvent:
    debate_context = "\n\n".join(
        f"### {role}\n{content}" for role, content in state.agent_outputs.items()
    )
    proposers_str = ", ".join(topology.proposers)
    evaluator_name = topology.evaluator or ""
    implementers_str = ", ".join(topology.implementers)

    consolidation_prompt = _CONSOLIDATION_PROMPT.format(
        supervisor_name=supervisor_name,
        proposers_str=proposers_str,
        evaluator_name=evaluator_name,
        implementers_str=implementers_str,
        debate_context=debate_context,
    )
    
    start_time = time.perf_counter()
    final_response = await asyncio.to_thread(default_provider.complete, consolidation_prompt, default_model)
    latency = round(time.perf_counter() - start_time, 2)

    usage = {}
    if hasattr(default_provider, "get_last_usage"):
        usage = default_provider.get_last_usage() or {}

    if not usage or usage.get("total", 0) == 0:
        in_tkn = max(1, len(consolidation_prompt) // 4)
        out_tkn = max(1, len(final_response) // 4)
        usage = {"input": in_tkn, "output": out_tkn, "total": in_tkn + out_tkn}

    meta = {
        "model": default_model,
        "prompt_tokens": str(usage.get("input", 0)),
        "completion_tokens": str(usage.get("output", 0)),
        "total_tokens": str(usage.get("total", 0)),
        "latency_seconds": str(latency),
        "tokens": str(usage.get("total", 0)),
    }

    return SupervisorEvent(
        type=EventType.DONE,
        role=supervisor_name,
        content=final_response,
        metadata=meta,
    )
