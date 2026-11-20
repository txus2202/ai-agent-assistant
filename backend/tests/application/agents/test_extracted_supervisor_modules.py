"""
Unit tests for decomposed supervisor modules (`triage_service`, `debate_phases`, `consolidation_service`).
"""
from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from src.application.agents.consolidation_service import run_consolidation
from src.application.agents.debate_phases import (
    apply_phase_hitl_decision,
    determine_retry_targets,
    run_hitl_phase_loop,
)
from src.application.agents.debate_state import DebateState
from src.application.agents.triage_service import TriageDecision, classify_intent
from src.domain.agents.debate_topology import DebateTopology
from src.domain.agents.sub_agent_profiles import SubAgentProfile
from src.domain.agents.supervisor_events import EventType, HITLDecision, HITLResponse, SupervisorEvent
from src.infrastructure.config.yaml_agent_catalog import InMemoryAgentCatalogRepository


def _catalog() -> InMemoryAgentCatalogRepository:
    return InMemoryAgentCatalogRepository([
        SubAgentProfile(
            id="sup",
            display_name="Coord",
            description="Lead coordinator",
            color_hex="#111111",
            system_prompt="Coord prompt",
            is_supervisor=True,
        ),
        SubAgentProfile(
            id="interp",
            display_name="Interp",
            description="Interpreter",
            color_hex="#222222",
            system_prompt="Interp prompt",
        ),
        SubAgentProfile(
            id="spec_a",
            display_name="SpecA",
            description="Specialist A",
            color_hex="#333333",
            system_prompt="SpecA prompt",
        ),
    ])


def test_triage_logs_warning_and_falls_back_on_llm_error(caplog):
    llm = MagicMock()
    llm.complete.side_effect = RuntimeError("provider timeout")

    with caplog.at_level(logging.WARNING, logger="src.application.agents.triage_service"):
        decision = classify_intent(
            "Diseñar sistema distribuido",
            llm,
            "m",
            supervisor_name="Coord",
            interpreter_name="Interp",
            agent_catalog=_catalog(),
        )

    assert decision == TriageDecision(
        mode="adaptive_debate",
        target_agent=None,
        skip_interpreter=False,
        reasoning="Fallback estándar",
    )
    assert "LLM triage failed" in caplog.text


@pytest.mark.anyio
async def test_run_hitl_phase_loop_handles_retry_then_approve():
    state = DebateState()
    rounds_run: list[tuple[str, ...]] = []

    async def _round_stream(roles: tuple[str, ...], refinement: str):
        rounds_run.append(roles)
        for role in roles:
            # First run simulates failure; retry succeeds
            if len(rounds_run) == 1:
                state.agent_outputs[role] = f"[Error en {role}]"
            else:
                state.agent_outputs[role] = f"Resolved for {role}"
        yield SupervisorEvent(type=EventType.AGENT_COMPLETED, role=roles[0], content="round")

    responses = iter([
        HITLResponse(decision=HITLDecision.RETRY),
        HITLResponse(decision=HITLDecision.APPROVE),
    ])

    async def _hitl_callback(_ev: SupervisorEvent) -> HITLResponse:
        return next(responses)

    events: list[SupervisorEvent] = []
    async for ev in run_hitl_phase_loop(
        state,
        ("Interp",),
        _hitl_callback,
        _round_stream,
        lambda hitl, combined: apply_phase_hitl_decision(
            state, hitl, lambda _r: setattr(state, "formalized", combined)
        ),
    ):
        events.append(ev)

    assert len(rounds_run) == 2
    assert any(e.type == EventType.HITL_REQUIRED and e.metadata.get("error_recovery") == "true" for e in events)
    assert state.formalized == "Resolved for Interp"


def test_determine_retry_targets_falls_back_to_all_when_none_failed():
    state = DebateState()
    state.agent_outputs["A"] = "ok"
    state.agent_outputs["B"] = "[Fallo en B]"

    assert determine_retry_targets(("A", "B"), state) == ("B",)
    state.agent_outputs["B"] = "ok"
    assert determine_retry_targets(("A", "B"), state) == ("A", "B")


@pytest.mark.anyio
async def test_consolidation_service_builds_done_event():
    state = DebateState()
    state.agent_outputs["SpecA"] = "Salida A"
    topology = DebateTopology(
        supervisor="Coord",
        proposers=("SpecA",),
        evaluators=("Interp",),
        implementers=("SpecA",),
    )
    llm = MagicMock()
    llm.complete.return_value = "Dictamen final"

    ev = await run_consolidation(state, llm, "m", supervisor_name="Coord", topology=topology)
    assert ev.type == EventType.DONE
    assert ev.role == "Coord"
    assert ev.content == "Dictamen final"

