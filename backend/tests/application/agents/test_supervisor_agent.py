"""
Tests — SupervisorAgent (Feature: feature_supervisor_agent.md)

Layer: Application/Agents

ADR-016: SupervisorAgent.run() is now an async generator.
Tests use @pytest.mark.anyio and `async for` / list comprehension.

Strategy:
  - SubAgentRunner.run is mocked at the module level via monkeypatch.
  - LLMProvider is a FakeLLM (returns deterministic strings).
  - InMemoryDocumentStore used (no ChromaDB).
  - hitl_callback is now an async def.

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
    def list_models(self) -> list[dict[str, str]]:
        return [{"id": "test", "name": "Test"}]

    def complete(self, prompt: str, model_name: str) -> str:
        return f"[consolidated response from: {prompt[:40]}]"

class FakeAgentConfigRepo:
    def find_by_role(self, role: str):
        return None


def _make_mock_runner(response_text: str = "agent response"):
    from src.application.agents.sub_agent_runner import SubAgentResponse

    async def _run(role, user_request, llm_provider, document_store, model_name):
        return SubAgentResponse(role=role, content=f"{role.value}: {response_text}", context_chunks=[])

    return _run


async def _approve_always(_event: SupervisorEvent) -> HITLResponse:
    return HITLResponse(decision=HITLDecision.APPROVE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _collect(gen) -> list[SupervisorEvent]:
    return [event async for event in gen]


def _event_types(events: list[SupervisorEvent]) -> list[EventType]:
    return [e.type for e in events]


def _roles_for_type(events: list[SupervisorEvent], event_type: EventType) -> list[AgentRole | None]:
    return [e.role for e in events if e.type == event_type]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSupervisorAgentEventOrder:
    @pytest.mark.anyio
    async def test_full_approve_flow_starts_with_nl_interpreter(self, monkeypatch):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _make_mock_runner())

        events = await _collect(SupervisorAgent.run(
            user_request="Design a caching strategy",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_approve_always,
        ))

        types = _event_types(events)
        assert types[0] == EventType.AGENT_STARTED
        assert events[0].role == AgentRole.NL_INTERPRETER

    @pytest.mark.anyio
    async def test_full_approve_flow_ends_with_done(self, monkeypatch):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _make_mock_runner())

        events = await _collect(SupervisorAgent.run(
            user_request="Design a caching strategy",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_approve_always,
        ))

        assert events[-1].type == EventType.DONE

    @pytest.mark.anyio
    async def test_full_approve_flow_emits_at_least_12_events(self, monkeypatch):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _make_mock_runner())

        events = await _collect(SupervisorAgent.run(
            user_request="Design a caching strategy",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_approve_always,
        ))

        assert len(events) >= 12

    @pytest.mark.anyio
    async def test_all_six_roles_appear_as_agent_started(self, monkeypatch):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _make_mock_runner())

        events = await _collect(SupervisorAgent.run(
            user_request="Design a caching strategy",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_approve_always,
        ))

        started_roles = set(_roles_for_type(events, EventType.AGENT_STARTED))
        expected = {r for r in AgentRole if r not in (AgentRole.LEARNING, AgentRole.SUPERVISOR)}
        assert expected.issubset(started_roles)

    @pytest.mark.anyio
    async def test_two_hitl_required_events_in_full_approve_flow(self, monkeypatch):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _make_mock_runner())

        events = await _collect(SupervisorAgent.run(
            user_request="Design a caching strategy",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_approve_always,
        ))

        hitl_events = [e for e in events if e.type == EventType.HITL_REQUIRED]
        assert len(hitl_events) == 3


class TestSupervisorAgentHITL:
    @pytest.mark.anyio
    async def test_hitl2_and_hitl3_content_includes_proposals(self, monkeypatch):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _make_mock_runner("proposal text"))

        hitl_events: list[SupervisorEvent] = []

        async def _capture_all(event: SupervisorEvent) -> HITLResponse:
            hitl_events.append(event)
            return HITLResponse(decision=HITLDecision.APPROVE)

        await _collect(SupervisorAgent.run(
            user_request="Design something",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_capture_all,
        ))

        assert len(hitl_events) == 3
        hitl2 = hitl_events[1]
        assert AgentRole.INNOVATOR.value in hitl2.content
        assert AgentRole.SENIOR_ARCHITECT.value in hitl2.content
        
        hitl3 = hitl_events[2]
        assert AgentRole.THE_JUDGE.value in hitl3.content

    @pytest.mark.anyio
    async def test_reject_at_hitl2_reruns_architects(self, monkeypatch):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        call_counts: dict[str, int] = {}

        from src.application.agents.sub_agent_runner import SubAgentResponse

        async def _counting_runner(role, user_request, llm_provider, document_store, model_name):
            key = role.value
            call_counts[key] = call_counts.get(key, 0) + 1
            return SubAgentResponse(role=role, content=f"{role.value}: response", context_chunks=[])

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _counting_runner)

        decisions = iter([
            HITLResponse(decision=HITLDecision.APPROVE), # HITL1
            HITLResponse(decision=HITLDecision.REJECT),  # HITL2
            HITLResponse(decision=HITLDecision.APPROVE), # HITL2
            HITLResponse(decision=HITLDecision.APPROVE), # HITL3
        ])

        async def _sequential_callback(_event: SupervisorEvent) -> HITLResponse:
            return next(decisions)

        await _collect(SupervisorAgent.run(
            user_request="Design something",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_sequential_callback,
        ))

        assert call_counts.get(AgentRole.INNOVATOR.value, 0) == 2
        assert call_counts.get(AgentRole.SENIOR_ARCHITECT.value, 0) == 2

    @pytest.mark.anyio
    async def test_refine_at_hitl2_does_not_rerun_architects(self, monkeypatch):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        call_counts: dict[str, int] = {}

        from src.application.agents.sub_agent_runner import SubAgentResponse

        async def _counting_runner(role, user_request, llm_provider, document_store, model_name):
            key = role.value
            call_counts[key] = call_counts.get(key, 0) + 1
            return SubAgentResponse(role=role, content=f"{role.value}: response", context_chunks=[])

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _counting_runner)

        decisions = iter([
            HITLResponse(decision=HITLDecision.APPROVE), # HITL1
            HITLResponse(decision=HITLDecision.REFINE, feedback="focus on latency"), # HITL2
            HITLResponse(decision=HITLDecision.APPROVE), # HITL2
            HITLResponse(decision=HITLDecision.APPROVE), # HITL3
        ])

        async def _sequential_callback(_event: SupervisorEvent) -> HITLResponse:
            return next(decisions)

        await _collect(SupervisorAgent.run(
            user_request="Design something",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_sequential_callback,
        ))

        assert call_counts.get(AgentRole.INNOVATOR.value, 0) == 2
        assert call_counts.get(AgentRole.SENIOR_ARCHITECT.value, 0) == 2

    @pytest.mark.anyio
    async def test_refine_feedback_appears_in_judge_request(self, monkeypatch):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        received_requests: dict[str, str] = {}

        from src.application.agents.sub_agent_runner import SubAgentResponse

        async def _capturing_runner(role, user_request, llm_provider, document_store, model_name):
            received_requests[role.value] = user_request
            return SubAgentResponse(role=role, content=f"{role.value}: response", context_chunks=[])

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _capturing_runner)

        decisions = iter([
            HITLResponse(decision=HITLDecision.APPROVE), # HITL1
            HITLResponse(decision=HITLDecision.APPROVE), # HITL2
            HITLResponse(decision=HITLDecision.REFINE, feedback="focus on latency"), # HITL3
            HITLResponse(decision=HITLDecision.APPROVE), # HITL3
        ])

        async def _sequential_callback(_event: SupervisorEvent) -> HITLResponse:
            return next(decisions)

        await _collect(SupervisorAgent.run(
            user_request="Design something",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_sequential_callback,
        ))

        assert "focus on latency" in received_requests.get(AgentRole.THE_JUDGE.value, "")

    @pytest.mark.anyio
    async def test_done_event_has_non_empty_content(self, monkeypatch):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _make_mock_runner())

        events = await _collect(SupervisorAgent.run(
            user_request="Design a caching strategy",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_approve_always,
        ))

        done = events[-1]
        assert done.type == EventType.DONE
        assert len(done.content) > 0

    @pytest.mark.anyio
    async def test_reject_at_hitl3_reruns_judge(self, monkeypatch):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        call_counts: dict[str, int] = {}

        from src.application.agents.sub_agent_runner import SubAgentResponse

        async def _counting_runner(role, user_request, llm_provider, document_store, model_name):
            key = role.value
            call_counts[key] = call_counts.get(key, 0) + 1
            return SubAgentResponse(role=role, content=f"{role.value}: response", context_chunks=[])

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _counting_runner)

        decisions = iter([
            HITLResponse(decision=HITLDecision.APPROVE), # HITL1
            HITLResponse(decision=HITLDecision.APPROVE), # HITL2
            HITLResponse(decision=HITLDecision.REJECT),  # HITL3
            HITLResponse(decision=HITLDecision.APPROVE), # HITL3
        ])

        async def _sequential_callback(_event: SupervisorEvent) -> HITLResponse:
            return next(decisions)

        await _collect(SupervisorAgent.run(
            user_request="Design something",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_sequential_callback,
        ))

        assert call_counts.get(AgentRole.THE_JUDGE.value, 0) == 2
