"""
Application Agent: SupervisorAgent

Orchestrates a multi-agent debate through a typed async event stream.
Returns an AsyncGenerator[SupervisorEvent, None] — compatible with WebSocket
streaming (ADR-016) and iteration in tests.

This module does NOT know which agents take part in the debate. They are resolved
through the declarative topology (topology.yaml) and the agent registry
(agents.yaml), so adding, removing or renaming agents never requires touching it.

Cohesive collaborators extracted per SRP:
  - ``triage_service.py``: ``TriageDecision``, ``classify_intent``
  - ``debate_state.py``: ``DebateState`` & stage markers
  - ``debate_phases.py``: unified ``run_hitl_phase_loop``, ``run_parallel_roles``, phases 1–4
  - ``consolidation_service.py``: ``CONSOLIDATION_PROMPT``, ``run_consolidation``
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any

from src.application.agents.consolidation_service import (
    CONSOLIDATION_PROMPT as _CONSOLIDATION_PROMPT,
    run_consolidation as _run_consolidation,
)
from src.application.agents.debate_phases import (
    HitlCallback,
    RoleRunner,
    constant_prompt,
    execute_phase_1_interpreters as _run_phase_1,
    execute_phase_2_proposers as _run_phase_2,
    execute_phase_3_evaluators as _run_phase_3,
    execute_phase_4_implementers as _run_phase_4,
    execute_role_safely as _execute_role_safely,
    run_parallel_roles,
)
from src.application.agents.debate_state import (
    ERROR_MARKER,
    FAILURE_MARKER,
    SECTION_SEPARATOR,
    DebateState,
)
from src.application.agents.sub_agent_runner import SubAgentRunner
from src.application.agents.triage_service import TriageDecision, classify_intent
from src.domain.agents.debate_topology import DebateTopology
from src.domain.agents.sub_agent_profiles import SubAgentProfile, format_team_roster
from src.domain.agents.supervisor_events import (
    EventType,
    HITLDecision,
    HITLResponse,
    SupervisorEvent,
)
from src.domain.ports.agent_catalog_repository import IAgentCatalogRepository, ITopologyProvider
from src.domain.ports.document_store import IDocumentStore
from src.domain.ports.image_generator import IImageGenerator
from src.domain.ports.llm_provider import ILLMProvider

__all__ = [
    "DebateRunOptions",
    "DebateState",
    "SupervisorAgent",
    "TriageDecision",
    "_CONSOLIDATION_PROMPT",
    "_run_consolidation",
    "_run_phase_1",
    "_run_phase_2",
    "_run_phase_3",
    "_run_phase_4",
    "classify_intent",
]

_DEFAULT_PROVIDER = "gemini"
_DEFAULT_MODEL = "gemini-3.6-flash"


@dataclass(frozen=True, slots=True)
class DebateRunOptions:
    """Optional runtime overrides for ``SupervisorAgent.run``."""

    default_provider: str = _DEFAULT_PROVIDER
    default_model: str = _DEFAULT_MODEL
    image_generator: IImageGenerator | None = None


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
        cancel_event: asyncio.Event | None = None,
        agent_catalog: IAgentCatalogRepository | None = None,
        topology_provider: ITopologyProvider | None = None,
        options: DebateRunOptions | None = None,
    ) -> AsyncGenerator[SupervisorEvent, None]:
        """Run the full debate flow and yield SupervisorEvents asynchronously (ADR-016)."""
        return _debate_generator(
            user_request=user_request,
            document_store=document_store,
            agent_config_repo=agent_config_repo,
            llm_factory=llm_factory,
            hitl_callback=hitl_callback,
            chat_history=chat_history,
            review_rounds=review_rounds,
            topology=topology,
            cancel_event=cancel_event,
            agent_catalog=agent_catalog,
            topology_provider=topology_provider,
            options=options,
        )


def _determine_review_rounds(review_rounds: int | None) -> int:
    return review_rounds if review_rounds is not None else 1


def _resolve_supervisor_config(
    agent_config_repo: Any,
    profile: Any,
    default_provider: str = _DEFAULT_PROVIDER,
    default_model: str = _DEFAULT_MODEL,
) -> tuple[str, str]:
    config = agent_config_repo.find_by_role(profile.display_name) or agent_config_repo.find_by_role(profile.id)
    default_prov = getattr(profile, "default_provider", "") or default_provider
    default_mod = getattr(profile, "default_model", "") or default_model
    provider_name = config.provider if (config and config.provider) else default_prov
    model_name = config.model_name if (config and config.model_name) else default_mod
    return provider_name, model_name


async def _stream_llm_completion(
    provider: Any,
    prompt: str,
    model_name: str,
) -> AsyncGenerator[str, None]:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[Any] = asyncio.Queue()

    def _producer() -> None:
        try:
            if hasattr(provider, "complete_stream"):
                for piece in provider.complete_stream(prompt, model_name):
                    loop.call_soon_threadsafe(queue.put_nowait, piece)
            else:
                piece = provider.complete(prompt, model_name)
                loop.call_soon_threadsafe(queue.put_nowait, piece)
        except Exception as e:
            loop.call_soon_threadsafe(queue.put_nowait, e)
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    producer_task = asyncio.create_task(asyncio.to_thread(_producer))
    try:
        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item
    finally:
        await producer_task


async def _run_direct_chat_mode(
    user_request: str,
    chat_history: list[dict[str, Any]] | None,
    supervisor_profile: Any,
    supervisor_provider: Any,
    sup_agent_name: str,
    sup_model_name: str,
    agent_catalog: IAgentCatalogRepository,
) -> AsyncGenerator[SupervisorEvent, None]:
    yield SupervisorEvent(type=EventType.AGENT_STARTED, role=sup_agent_name, content="")

    hist_lines = [
        f"- {m.get('role', 'user')}: {m.get('content', '')}"
        for m in (chat_history or ())
    ]
    roster_context = format_team_roster(
        agent_catalog.get_all_profiles(),
        exclude_id=supervisor_profile.id,
    )
    direct_prompt = (
        f"# HISTORIAL DE CONVERSACIÓN\n{chr(10).join(hist_lines) or 'Sin historial previo.'}\n\n"
        f"# INSTRUCCIÓN DE SISTEMA\n{supervisor_profile.system_prompt}\n\n"
        f"{roster_context}\n\n"
        f"# MENSAJE DEL USUARIO\n{user_request}\n\n"
        f"Responde directamente al usuario como {sup_agent_name} en español, manteniendo la personalidad y el tono definidos en tu instrucción de sistema. Si te piden presentar al equipo o sus miembros y funciones, básate estrictamente en la información oficial y veraz del consejo técnico."
    )
    start_time = time.perf_counter()
    resp_pieces: list[str] = []
    async for piece in _stream_llm_completion(supervisor_provider, direct_prompt, sup_model_name):
        resp_pieces.append(piece)
        yield SupervisorEvent(type=EventType.STREAM_CHUNK, role=sup_agent_name, content=piece)

    resp_text = "".join(resp_pieces)
    latency = round(time.perf_counter() - start_time, 2)
    raw_usage = supervisor_provider.get_last_usage() if hasattr(supervisor_provider, "get_last_usage") else {}
    provider_usage = raw_usage if isinstance(raw_usage, dict) else {}
    in_tkn = provider_usage.get("input", 0) or max(15, len(direct_prompt) // 4)
    out_tkn = provider_usage.get("output", 0) or max(10, len(resp_text) // 4)
    hist_chars = sum(len(line) for line in hist_lines)
    cached_tkn = provider_usage.get("cached", 0) or (
        min(in_tkn, max(1, hist_chars // 4)) if hist_chars > 0 else 0
    )
    meta = {
        "model": sup_model_name,
        "latency_seconds": str(latency),
        "prompt_tokens": str(in_tkn),
        "completion_tokens": str(out_tkn),
        "total_tokens": str(in_tkn + out_tkn),
        "tokens": str(in_tkn + out_tkn),
        "cached_tokens": str(cached_tkn),
    }
    yield SupervisorEvent(type=EventType.AGENT_COMPLETED, role=sup_agent_name, content=resp_text, metadata=meta)
    yield SupervisorEvent(
        type=EventType.DONE,
        role=sup_agent_name,
        content=resp_text,
        metadata={"model": sup_model_name, "metrics_reported": "true"},
    )


async def _run_single_agent_mode(
    target_agent: str,
    user_request: str,
    run_role: RoleRunner,
    state: DebateState,
    agent_catalog: IAgentCatalogRepository,
) -> AsyncGenerator[SupervisorEvent, None]:
    target_name = agent_catalog.get_profile(target_agent).display_name
    yield SupervisorEvent(type=EventType.AGENT_STARTED, role=target_name, content="")
    _, content, error = await _execute_role_safely(target_name, user_request, run_role, agent_catalog=agent_catalog)
    meta = state.agent_metadata.get(target_name, {})
    if error:
        yield SupervisorEvent(
            type=EventType.ERROR,
            role=target_name,
            content=f"Error en {target_name}: {error}",
            metadata={"fatal": "false", "agent": target_name},
        )
        content = f"Error al generar respuesta en {target_name}: {error}"
    else:
        yield SupervisorEvent(type=EventType.AGENT_COMPLETED, role=target_name, content=content, metadata=meta)
    done_meta = {"metrics_reported": "true"}
    model_val = meta.get("model") if isinstance(meta, dict) else None
    if model_val:
        done_meta["model"] = model_val
    yield SupervisorEvent(type=EventType.DONE, role=target_name, content=content, metadata=done_meta)


def _resolve_target_agents(agent_names: list[str], agent_catalog: IAgentCatalogRepository) -> list[str]:
    resolved: list[str] = []
    for name in agent_names:
        try:
            resolved.append(agent_catalog.get_profile(name).display_name)
        except KeyError:
            resolved.append(name)
    return resolved


def _build_divert_hitl_event(current_targets: list[str], outputs: dict[str, str]) -> SupervisorEvent:
    lead_agent = current_targets[0]
    has_error = any(
        any(marker in outputs.get(r, "") for marker in (FAILURE_MARKER, ERROR_MARKER))
        for r in current_targets
    )
    hitl_metadata = {"checkpoint": f"after_divert_{lead_agent}", "agent": lead_agent}
    if has_error:
        hitl_metadata["error_recovery"] = "true"
    combined_content = SECTION_SEPARATOR.join(outputs.get(r, "") for r in current_targets)
    return SupervisorEvent(
        type=EventType.HITL_REQUIRED,
        role=lead_agent,
        content=combined_content,
        metadata=hitl_metadata,
    )


def _apply_divert_continuation(hitl: HITLResponse, state: DebateState, current_targets: list[str]) -> None:
    state.target_agents = hitl.target_agents or current_targets
    if hitl.feedback:
        state.refinement = hitl.feedback


async def _maybe_divert_to_targets(
    state: DebateState,
    run_role: RoleRunner,
    hitl_callback: HitlCallback,
    supervisor_provider: Any,
    sup_model_name: str,
    sup_agent_name: str,
    active_topology: DebateTopology,
    agent_catalog: IAgentCatalogRepository,
) -> AsyncGenerator[SupervisorEvent, None]:
    while state.target_agents:
        target_agents = _resolve_target_agents(state.target_agents, agent_catalog)
        if not target_agents:
            break
        current_targets = list(target_agents)
        state.target_agents = []

        req = state.formalized + (f"\n\n## User Refinement\n{state.refinement}" if state.refinement else "")
        async for event in run_parallel_roles(
            tuple(current_targets),
            constant_prompt(req),
            run_role,
            state,
            error_format="[Fallo en {role}: {error}]",
            emit_message=True,
            agent_catalog=agent_catalog,
        ):
            yield event

        hitl_event = _build_divert_hitl_event(current_targets, state.agent_outputs)
        yield hitl_event
        hitl = await hitl_callback(hitl_event)

        if hitl.decision == HITLDecision.FINISH:
            state.finish_early = True
            state.skip_consolidation = True
            yield SupervisorEvent(
                type=EventType.DONE,
                role=sup_agent_name,
                content="Debate finalizado por el usuario tras desvío sin consolidación.",
                metadata={"skip_consolidation": "true"},
            )
            return

        if hitl.decision in (HITLDecision.CONSOLIDATE, HITLDecision.APPROVE):
            state.finish_early = True
            yield await _run_consolidation(
                state,
                supervisor_provider,
                sup_model_name,
                supervisor_name=sup_agent_name,
                topology=active_topology,
            )
            return

        _apply_divert_continuation(hitl, state, current_targets)

    state.finish_early = True
    yield await _run_consolidation(
        state,
        supervisor_provider,
        sup_model_name,
        supervisor_name=sup_agent_name,
        topology=active_topology,
    )


def _resolve_role_llm_settings(
    cfg: Any,
    profile: SubAgentProfile,
    default_provider: str,
    default_model: str,
) -> tuple[str, str]:
    fallback_prov = getattr(profile, "default_provider", "") or default_provider
    fallback_mod = getattr(profile, "default_model", "") or default_model
    prov_name = cfg.provider if (cfg and getattr(cfg, "provider", None)) else fallback_prov
    mod_name = cfg.model_name if (cfg and getattr(cfg, "model_name", None)) else fallback_mod
    return prov_name, mod_name


def _build_runner_kwargs(
    config: Any,
    chat_history: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if chat_history:
        kwargs["chat_history"] = chat_history
    if config:
        if getattr(config, "rag_top_k", None) is not None:
            kwargs["rag_top_k"] = config.rag_top_k
        if getattr(config, "rag_min_score", None) is not None:
            kwargs["rag_min_score"] = config.rag_min_score
    return kwargs


def _record_agent_response_metadata(
    state: DebateState,
    agent_name: str,
    profile_id: str,
    resp: Any,
    fallback_model: str,
    req: str,
) -> None:
    in_tkn = resp.tokens.get("input", 0)
    cached_tkn = resp.tokens.get("cached", 0)
    if not cached_tkn and state.debate_history and req:
        cached_tkn = min(in_tkn, max(1, len(req) // 4))
    meta = {
        "model": resp.model_name or fallback_model,
        "prompt_tokens": str(in_tkn),
        "completion_tokens": str(resp.tokens.get("output", 0)),
        "total_tokens": str(resp.tokens.get("total", 0)),
        "latency_seconds": str(resp.latency),
        "tokens": str(resp.tokens.get("total", 0)),
        "cached_tokens": str(cached_tkn),
    }
    state.agent_metadata[agent_name] = meta
    state.agent_metadata[profile_id] = meta
    state.agent_outputs[profile_id] = resp.content
    state.agent_outputs[agent_name] = resp.content
    state.debate_history.append({"role": "assistant", "name": agent_name, "content": resp.content})


def _build_role_runner(
    agent_config_repo: Any,
    document_store: IDocumentStore,
    llm_factory: Callable[[str], ILLMProvider],
    default_provider: str,
    default_model: str,
    chat_history: list[dict[str, Any]] | None,
    state: DebateState,
    agent_catalog: IAgentCatalogRepository,
    image_generator: IImageGenerator | None = None,
) -> RoleRunner:
    async def run_role(role: str, req: str) -> tuple[str, str]:
        profile = agent_catalog.get_profile(role)
        agent_name = profile.display_name

        def _resolve_role_sync() -> tuple[Any, str, ILLMProvider]:
            cfg = agent_config_repo.find_by_role(agent_name) or agent_config_repo.find_by_role(profile.id)
            prov_name, mod_name = _resolve_role_llm_settings(cfg, profile, default_provider, default_model)
            return cfg, mod_name, llm_factory(prov_name)

        config, model_name, llm_provider = await asyncio.to_thread(_resolve_role_sync)
        runner_kwargs = _build_runner_kwargs(config, chat_history)

        resp = await SubAgentRunner.run(
            role=agent_name,
            user_request=req,
            llm_provider=llm_provider,
            document_store=document_store,
            model_name=model_name,
            agent_catalog=agent_catalog,
            image_generator=image_generator,
            **runner_kwargs,
        )
        _record_agent_response_metadata(state, agent_name, profile.id, resp, model_name, req)
        return agent_name, resp.content

    return run_role


def _build_planned_stages(triage: Any, active_topology: DebateTopology) -> list[str]:
    if triage and getattr(triage, "execution_plan", None):
        valid_slots = {"interpreters", "proposers", "evaluators", "implementers"}
        stages = [s for s in triage.execution_plan if s in valid_slots]
        if stages:
            return stages

    plan: list[str] = []
    skip_interp = bool(triage and getattr(triage, "skip_interpreter", False))
    if active_topology.interpreters and not skip_interp:
        plan.append("interpreters")
    for slot_name in ("proposers", "evaluators", "implementers"):
        if getattr(active_topology, slot_name, ()):
            plan.append(slot_name)
    return plan


def _build_stage_stream(
    stage: str,
    state: DebateState,
    user_request: str,
    run_role: RoleRunner,
    hitl_callback: HitlCallback,
    active_topology: DebateTopology,
    effective_review_rounds: int,
) -> AsyncGenerator[SupervisorEvent, None] | None:
    if stage == "interpreters" and active_topology.interpreters:
        return _run_phase_1(state, user_request, run_role, hitl_callback, active_topology.interpreters)
    if stage == "proposers" and active_topology.proposers:
        return _run_phase_2(
            state,
            run_role,
            hitl_callback,
            active_topology.proposers,
            active_topology.reviewers,
            effective_review_rounds,
        )
    if stage == "evaluators" and active_topology.evaluators:
        return _run_phase_3(state, run_role, hitl_callback, active_topology.evaluators)
    return None


async def _execute_single_stage(
    stage: str,
    state: DebateState,
    user_request: str,
    run_role: RoleRunner,
    hitl_callback: HitlCallback,
    active_topology: DebateTopology,
    effective_review_rounds: int,
    supervisor_provider: Any,
    sup_model_name: str,
    sup_agent_name: str,
    agent_catalog: IAgentCatalogRepository,
) -> AsyncGenerator[SupervisorEvent, None]:
    if stage == "implementers":
        async for event in _run_phase_4(state, run_role, active_topology.implementers):
            yield event
        return

    phase_stream = _build_stage_stream(
        stage, state, user_request, run_role, hitl_callback, active_topology, effective_review_rounds
    )
    if not phase_stream:
        return

    async for event in phase_stream:
        yield event
    if state.target_agents:
        async for event in _maybe_divert_to_targets(
            state,
            run_role,
            hitl_callback,
            supervisor_provider,
            sup_model_name,
            sup_agent_name,
            active_topology,
            agent_catalog,
        ):
            yield event
        return
    if state.finish_early and not state.target_agents:
        if state.skip_consolidation:
            yield SupervisorEvent(
                type=EventType.DONE,
                role=sup_agent_name,
                content="Debate finalizado por el usuario sin consolidación.",
                metadata={"skip_consolidation": "true"},
            )
        else:
            yield await _run_consolidation(
                state,
                supervisor_provider,
                sup_model_name,
                supervisor_name=sup_agent_name,
                topology=active_topology,
            )


async def _run_adaptive_debate(
    state: DebateState,
    user_request: str,
    run_role: RoleRunner,
    hitl_callback: HitlCallback,
    triage: Any,
    active_topology: DebateTopology,
    effective_review_rounds: int,
    supervisor_provider: Any,
    sup_model_name: str,
    sup_agent_name: str,
    agent_catalog: IAgentCatalogRepository,
    cancel_event: asyncio.Event | None = None,
) -> AsyncGenerator[SupervisorEvent, None]:
    state.formalized = user_request
    for stage in _build_planned_stages(triage, active_topology):
        if cancel_event is not None and cancel_event.is_set():
            return
        async for event in _execute_single_stage(
            stage,
            state,
            user_request,
            run_role,
            hitl_callback,
            active_topology,
            effective_review_rounds,
            supervisor_provider,
            sup_model_name,
            sup_agent_name,
            agent_catalog,
        ):
            yield event
            if cancel_event is not None and cancel_event.is_set():
                return
        if state.finish_early or state.target_agents:
            return

    if cancel_event is not None and cancel_event.is_set():
        return
    yield await _run_consolidation(
        state, supervisor_provider, sup_model_name, supervisor_name=sup_agent_name, topology=active_topology
    )


def _resolve_interpreter_name(
    active_topology: DebateTopology,
    agent_catalog: IAgentCatalogRepository,
) -> str:
    if not active_topology.interpreters:
        return ""
    try:
        return agent_catalog.get_profile(active_topology.interpreters[0]).display_name
    except KeyError:
        return active_topology.interpreters[0]


async def _debate_generator(
    user_request: str,
    document_store: IDocumentStore,
    agent_config_repo: Any,
    llm_factory: Callable[[str], ILLMProvider],
    hitl_callback: HitlCallback,
    chat_history: list[dict[str, Any]] | None = None,
    review_rounds: int | None = None,
    topology: DebateTopology | None = None,
    cancel_event: asyncio.Event | None = None,
    agent_catalog: IAgentCatalogRepository | None = None,
    topology_provider: ITopologyProvider | None = None,
    options: DebateRunOptions | None = None,
) -> AsyncGenerator[SupervisorEvent, None]:
    if agent_catalog is None:
        raise ValueError("agent_catalog must be provided to SupervisorAgent.run()")

    active_topology = topology or (topology_provider.get_topology() if topology_provider else None)
    if active_topology is None:
        raise ValueError("Either topology or topology_provider must be provided to SupervisorAgent.run()")

    resolved_options = options or DebateRunOptions()
    state = DebateState()
    supervisor_profile = agent_catalog.get_profile(active_topology.supervisor)
    sup_agent_name = supervisor_profile.display_name
    sup_provider_name, sup_model_name = await asyncio.to_thread(
        _resolve_supervisor_config,
        agent_config_repo,
        supervisor_profile,
        resolved_options.default_provider,
        resolved_options.default_model,
    )
    supervisor_provider = await asyncio.to_thread(llm_factory, sup_provider_name)
    run_role = _build_role_runner(
        agent_config_repo,
        document_store,
        llm_factory,
        resolved_options.default_provider,
        resolved_options.default_model,
        chat_history,
        state,
        agent_catalog,
        image_generator=resolved_options.image_generator,
    )

    triage = await asyncio.to_thread(
        classify_intent,
        user_request,
        supervisor_provider,
        sup_model_name,
        supervisor_name=sup_agent_name,
        interpreter_name=_resolve_interpreter_name(active_topology, agent_catalog),
        agent_catalog=agent_catalog,
    )

    if triage.mode == "direct_chat":
        async for event in _run_direct_chat_mode(
            user_request,
            chat_history,
            supervisor_profile,
            supervisor_provider,
            sup_agent_name,
            sup_model_name,
            agent_catalog,
        ):
            yield event
        return

    if triage.mode == "single_agent" and triage.target_agent:
        async for event in _run_single_agent_mode(
            triage.target_agent,
            user_request,
            run_role,
            state,
            agent_catalog,
        ):
            yield event
        return

    async for event in _run_adaptive_debate(
        state,
        user_request,
        run_role,
        hitl_callback,
        triage,
        active_topology,
        _determine_review_rounds(review_rounds),
        supervisor_provider,
        sup_model_name,
        sup_agent_name,
        agent_catalog,
        cancel_event=cancel_event,
    ):
        yield event
