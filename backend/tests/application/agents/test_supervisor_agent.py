"""
RED Tests — SupervisorAgent (Feature: feature_supervisor_agent.md)

Layer: Application/Agents

Strategy:
  - SubAgentRunner.run is mocked at the module level via monkeypatch.
  - LLMProvider is a FakeLLM (returns deterministic strings).
  - InMemoryDocumentStore used (no ChromaDB).
  - hitl_callback is a simple function returning pre-configured decisions.

Scenarios covered:
  1. Full flow with all APPROVE → events in correct order
  2. HITL ① content includes INNOVATOR + SENIOR + JUDGE proposals
  3. REJECT at HITL ① → re-runs architects
  4. REFINE at HITL ① → carries feedback to DIAGRAMMER (no re-run)
  5. DONE event carries consolidated content
  6. Total events >= 12 for full approve flow
  + HITL ② reject re-runs DIAGRAMMER + DEVOPS
"""
from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock

import pytest

from src.domain.agents.agent_role import AgentRole
from src.domain.agents.supervisor_events import (
    EventType,
    HITLDecision,
    HITLResponse,
    SupervisorEvent,
)
from src.domain.ports.llm_provider import ILLMProvider
from src.infrastructure.rag.in_memory_document_store import InMemoryDocumentStore


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class FakeLLM(ILLMProvider):
    def complete(self, prompt: str, model_name: str) -> str:
        return f"[consolidated response from: {prompt[:40]}]"


def _make_mock_runner(response_text: str = "agent response"):
    """Returns a mock for SubAgentRunner.run that returns a SubAgentResponse-like object."""
    from src.application.agents.sub_agent_runner import SubAgentResponse

    def _run(role, user_request, llm_provider, document_store, model_name):
        return SubAgentResponse(role=role, content=f"{role.value}: {response_text}", context_chunks=[])

    return _run


def _approve_always(_event: SupervisorEvent) -> HITLResponse:
    return HITLResponse(decision=HITLDecision.APPROVE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect(gen: Generator) -> list[SupervisorEvent]:
    return list(gen)


def _event_types(events: list[SupervisorEvent]) -> list[EventType]:
    return [e.type for e in events]


def _roles_for_type(events: list[SupervisorEvent], event_type: EventType) -> list[AgentRole | None]:
    return [e.role for e in events if e.type == event_type]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSupervisorAgentEventOrder:
    def test_full_approve_flow_starts_with_nl_interpreter(self, monkeypatch):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _make_mock_runner())

        events = _collect(SupervisorAgent.run(
            user_request="Design a caching strategy",
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            model_name="gemini-1.5-flash",
            hitl_callback=_approve_always,
        ))

        types = _event_types(events)
        assert types[0] == EventType.AGENT_STARTED
        assert events[0].role == AgentRole.NL_INTERPRETER

    def test_full_approve_flow_ends_with_done(self, monkeypatch):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _make_mock_runner())

        events = _collect(SupervisorAgent.run(
            user_request="Design a caching strategy",
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            model_name="gemini-1.5-flash",
            hitl_callback=_approve_always,
        ))

        assert events[-1].type == EventType.DONE

    def test_full_approve_flow_emits_at_least_12_events(self, monkeypatch):
        """Scenario 6: 2 per agent × 6 agents + 2 HITL + 1 DONE = 15 minimum."""
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _make_mock_runner())

        events = _collect(SupervisorAgent.run(
            user_request="Design a caching strategy",
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            model_name="gemini-1.5-flash",
            hitl_callback=_approve_always,
        ))

        assert len(events) >= 12

    def test_all_six_roles_appear_as_agent_started(self, monkeypatch):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _make_mock_runner())

        events = _collect(SupervisorAgent.run(
            user_request="Design a caching strategy",
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            model_name="gemini-1.5-flash",
            hitl_callback=_approve_always,
        ))

        started_roles = set(_roles_for_type(events, EventType.AGENT_STARTED))
        expected = {r for r in AgentRole}
        assert expected.issubset(started_roles)

    def test_two_hitl_required_events_in_full_approve_flow(self, monkeypatch):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _make_mock_runner())

        events = _collect(SupervisorAgent.run(
            user_request="Design a caching strategy",
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            model_name="gemini-1.5-flash",
            hitl_callback=_approve_always,
        ))

        hitl_events = [e for e in events if e.type == EventType.HITL_REQUIRED]
        assert len(hitl_events) == 2


class TestSupervisorAgentHITL:
    def test_hitl1_content_includes_all_three_proposals(self, monkeypatch):
        """Scenario 2: HITL ① carries INNOVATOR + SENIOR + JUDGE output."""
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _make_mock_runner("proposal text"))

        hitl_events: list[SupervisorEvent] = []

        def _capture_first(event: SupervisorEvent) -> HITLResponse:
            hitl_events.append(event)
            return HITLResponse(decision=HITLDecision.APPROVE)

        _collect(SupervisorAgent.run(
            user_request="Design something",
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            model_name="gemini-1.5-flash",
            hitl_callback=_capture_first,
        ))

        first_hitl = hitl_events[0]
        assert AgentRole.INNOVATOR.value in first_hitl.content
        assert AgentRole.SENIOR_ARCHITECT.value in first_hitl.content
        assert AgentRole.THE_JUDGE.value in first_hitl.content

    def test_reject_at_hitl1_reruns_architects(self, monkeypatch):
        """Scenario 3: REJECT → architects invoked twice total."""
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        call_counts: dict[str, int] = {}

        from src.application.agents.sub_agent_runner import SubAgentResponse

        def _counting_runner(role, user_request, llm_provider, document_store, model_name):
            key = role.value
            call_counts[key] = call_counts.get(key, 0) + 1
            return SubAgentResponse(role=role, content=f"{role.value}: response", context_chunks=[])

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _counting_runner)

        decisions = iter([
            HITLResponse(decision=HITLDecision.REJECT),   # first checkpoint ①
            HITLResponse(decision=HITLDecision.APPROVE),  # second checkpoint ①
            HITLResponse(decision=HITLDecision.APPROVE),  # checkpoint ②
        ])

        def _sequential_callback(_event: SupervisorEvent) -> HITLResponse:
            return next(decisions)

        _collect(SupervisorAgent.run(
            user_request="Design something",
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            model_name="gemini-1.5-flash",
            hitl_callback=_sequential_callback,
        ))

        # INNOVATOR and SENIOR_ARCHITECT each invoked twice (once per iteration)
        assert call_counts.get(AgentRole.INNOVATOR.value, 0) == 2
        assert call_counts.get(AgentRole.SENIOR_ARCHITECT.value, 0) == 2

    def test_refine_at_hitl1_does_not_rerun_architects(self, monkeypatch):
        """Scenario 4 (partial): REFINE → architects invoked exactly once."""
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        call_counts: dict[str, int] = {}

        from src.application.agents.sub_agent_runner import SubAgentResponse

        def _counting_runner(role, user_request, llm_provider, document_store, model_name):
            key = role.value
            call_counts[key] = call_counts.get(key, 0) + 1
            return SubAgentResponse(role=role, content=f"{role.value}: response", context_chunks=[])

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _counting_runner)

        decisions = iter([
            HITLResponse(decision=HITLDecision.REFINE, feedback="focus on latency"),
            HITLResponse(decision=HITLDecision.APPROVE),
        ])

        def _sequential_callback(_event: SupervisorEvent) -> HITLResponse:
            return next(decisions)

        _collect(SupervisorAgent.run(
            user_request="Design something",
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            model_name="gemini-1.5-flash",
            hitl_callback=_sequential_callback,
        ))

        assert call_counts.get(AgentRole.INNOVATOR.value, 0) == 1
        assert call_counts.get(AgentRole.SENIOR_ARCHITECT.value, 0) == 1

    def test_refine_feedback_appears_in_diagrammer_request(self, monkeypatch):
        """Scenario 4: REFINE feedback forwarded to DIAGRAMMER."""
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        received_requests: dict[str, str] = {}

        from src.application.agents.sub_agent_runner import SubAgentResponse

        def _capturing_runner(role, user_request, llm_provider, document_store, model_name):
            received_requests[role.value] = user_request
            return SubAgentResponse(role=role, content=f"{role.value}: response", context_chunks=[])

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _capturing_runner)

        decisions = iter([
            HITLResponse(decision=HITLDecision.REFINE, feedback="focus on latency"),
            HITLResponse(decision=HITLDecision.APPROVE),
        ])

        def _sequential_callback(_event: SupervisorEvent) -> HITLResponse:
            return next(decisions)

        _collect(SupervisorAgent.run(
            user_request="Design something",
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            model_name="gemini-1.5-flash",
            hitl_callback=_sequential_callback,
        ))

        assert "focus on latency" in received_requests.get(AgentRole.DIAGRAMMER.value, "")

    def test_done_event_has_non_empty_content(self, monkeypatch):
        """Scenario 5: DONE carries consolidated response."""
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _make_mock_runner())

        events = _collect(SupervisorAgent.run(
            user_request="Design a caching strategy",
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            model_name="gemini-1.5-flash",
            hitl_callback=_approve_always,
        ))

        done = events[-1]
        assert done.type == EventType.DONE
        assert len(done.content) > 0

    def test_reject_at_hitl2_reruns_diagrammer_and_devops(self, monkeypatch):
        """REJECT at HITL ② re-runs DIAGRAMMER + DEVOPS_SECOPS."""
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        call_counts: dict[str, int] = {}

        from src.application.agents.sub_agent_runner import SubAgentResponse

        def _counting_runner(role, user_request, llm_provider, document_store, model_name):
            key = role.value
            call_counts[key] = call_counts.get(key, 0) + 1
            return SubAgentResponse(role=role, content=f"{role.value}: response", context_chunks=[])

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _counting_runner)

        decisions = iter([
            HITLResponse(decision=HITLDecision.APPROVE),  # checkpoint ①
            HITLResponse(decision=HITLDecision.REJECT),   # checkpoint ② first
            HITLResponse(decision=HITLDecision.APPROVE),  # checkpoint ② second
        ])

        def _sequential_callback(_event: SupervisorEvent) -> HITLResponse:
            return next(decisions)

        _collect(SupervisorAgent.run(
            user_request="Design something",
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            model_name="gemini-1.5-flash",
            hitl_callback=_sequential_callback,
        ))

        assert call_counts.get(AgentRole.DIAGRAMMER.value, 0) == 2
        assert call_counts.get(AgentRole.DEVOPS_SECOPS.value, 0) == 2
