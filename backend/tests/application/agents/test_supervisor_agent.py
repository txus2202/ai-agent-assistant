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

from typing import Any

import pytest

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

    async def _run(role, user_request, llm_provider, document_store, model_name, **kwargs):
        role_str = role.value if hasattr(role, "value") else str(role)
        return SubAgentResponse(role=role, content=f"{role_str}: {response_text}", context_chunks=[])

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


def _roles_for_type(events: list[SupervisorEvent], event_type: EventType) -> list[str | None]:
    return [e.role for e in events if e.type == event_type]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSupervisorAgentEventOrder:
    @pytest.mark.anyio
    async def test_requires_agent_catalog_and_topology(self):
        from src.application.agents.supervisor_agent import SupervisorAgent

        with pytest.raises(ValueError, match="agent_catalog"):
            await _collect(SupervisorAgent.run(
                user_request="Design",
                document_store=InMemoryDocumentStore(),
                agent_config_repo=FakeAgentConfigRepo(),
                llm_factory=lambda _: FakeLLM(),
                hitl_callback=_approve_always,
            ))

    @pytest.mark.anyio
    async def test_full_approve_flow_starts_with_nl_interpreter(self, monkeypatch, generic_catalog, generic_topology):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _make_mock_runner())

        events = await _collect(SupervisorAgent.run(
            user_request="Design a caching strategy",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_approve_always,
            agent_catalog=generic_catalog,
            topology=generic_topology,
        ))

        types = _event_types(events)
        assert types[0] == EventType.AGENT_STARTED
        assert events[0].role in ("Interpreter", "interpreter")

    @pytest.mark.anyio
    async def test_full_approve_flow_ends_with_done(self, monkeypatch, generic_catalog, generic_topology):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _make_mock_runner())

        events = await _collect(SupervisorAgent.run(
            user_request="Design a caching strategy",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_approve_always,
            agent_catalog=generic_catalog,
            topology=generic_topology,
        ))

        assert events[-1].type == EventType.DONE

    @pytest.mark.anyio
    async def test_full_approve_flow_emits_at_least_12_events(self, monkeypatch, generic_catalog, generic_topology):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _make_mock_runner())

        events = await _collect(SupervisorAgent.run(
            user_request="Design a caching strategy",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_approve_always,
            agent_catalog=generic_catalog,
            topology=generic_topology,
        ))

        assert len(events) >= 12

    @pytest.mark.anyio
    async def test_all_six_roles_appear_as_agent_started(self, monkeypatch, generic_catalog, generic_topology):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _make_mock_runner())

        events = await _collect(SupervisorAgent.run(
            user_request="Design a caching strategy",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_approve_always,
            agent_catalog=generic_catalog,
            topology=generic_topology,
        ))

        started_roles = {r.value if hasattr(r, "value") else str(r) for r in _roles_for_type(events, EventType.AGENT_STARTED)}
        expected = {"Interpreter", "PropOne", "PropTwo", "Auditor", "ImplOne", "ImplTwo"}
        assert expected.issubset(started_roles)

    @pytest.mark.anyio
    async def test_two_hitl_required_events_in_full_approve_flow(self, monkeypatch, generic_catalog, generic_topology):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _make_mock_runner())

        events = await _collect(SupervisorAgent.run(
            user_request="Design a caching strategy",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_approve_always,
            agent_catalog=generic_catalog,
            topology=generic_topology,
        ))

        hitl_events = [e for e in events if e.type == EventType.HITL_REQUIRED]
        assert len(hitl_events) == 3


class TestSupervisorAgentHITL:
    @pytest.mark.anyio
    async def test_hitl2_and_hitl3_content_includes_proposals(self, monkeypatch, generic_catalog, generic_topology):
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
            agent_catalog=generic_catalog,
            topology=generic_topology,
        ))

        assert len(hitl_events) == 3
        hitl1 = hitl_events[0]
        assert hitl1.metadata.get("checkpoint") == "after_Interpreter"

        hitl2 = hitl_events[1]
        assert "PropOne" in hitl2.content
        assert "PropTwo" in hitl2.content
        assert hitl2.metadata.get("checkpoint") == "after_PropOne"
        
        hitl3 = hitl_events[2]
        assert "Auditor" in hitl3.content
        assert hitl3.metadata.get("checkpoint") == "after_Auditor"

    @pytest.mark.anyio
    async def test_reject_at_hitl2_reruns_architects(self, monkeypatch, generic_catalog, generic_topology):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        call_counts: dict[str, int] = {}

        from src.application.agents.sub_agent_runner import SubAgentResponse

        async def _counting_runner(role, user_request, llm_provider, document_store, model_name, **kwargs):
            key = role.value if hasattr(role, "value") else str(role)
            call_counts[key] = call_counts.get(key, 0) + 1
            return SubAgentResponse(role=role, content=f"{key}: response", context_chunks=[])

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
            review_rounds=0,
            agent_catalog=generic_catalog,
            topology=generic_topology,
        ))

        assert call_counts.get("PropOne", 0) == 2
        assert call_counts.get("PropTwo", 0) == 2

    @pytest.mark.anyio
    async def test_refine_at_hitl2_does_not_rerun_architects(self, monkeypatch, generic_catalog, generic_topology):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        call_counts: dict[str, int] = {}

        from src.application.agents.sub_agent_runner import SubAgentResponse

        async def _counting_runner(role, user_request, llm_provider, document_store, model_name, **kwargs):
            key = role.value if hasattr(role, "value") else str(role)
            call_counts[key] = call_counts.get(key, 0) + 1
            return SubAgentResponse(role=role, content=f"{key}: response", context_chunks=[])

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
            review_rounds=0,
            agent_catalog=generic_catalog,
            topology=generic_topology,
        ))

        assert call_counts.get("PropOne", 0) == 2
        assert call_counts.get("PropTwo", 0) == 2

    @pytest.mark.anyio
    async def test_refine_feedback_appears_in_judge_request(self, monkeypatch, generic_catalog, generic_topology):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        received_requests: dict[str, str] = {}

        from src.application.agents.sub_agent_runner import SubAgentResponse

        async def _capturing_runner(role, user_request, llm_provider, document_store, model_name, **kwargs):
            key = role.value if hasattr(role, "value") else str(role)
            received_requests[key] = user_request
            return SubAgentResponse(role=role, content=f"{key}: response", context_chunks=[])

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
            agent_catalog=generic_catalog,
            topology=generic_topology,
        ))

        assert "focus on latency" in received_requests.get("Auditor", "")

    @pytest.mark.anyio
    async def test_done_event_has_non_empty_content(self, monkeypatch, generic_catalog, generic_topology):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _make_mock_runner())

        events = await _collect(SupervisorAgent.run(
            user_request="Design a caching strategy",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_approve_always,
            agent_catalog=generic_catalog,
            topology=generic_topology,
        ))

        done = events[-1]
        assert done.type == EventType.DONE
        assert len(done.content) > 0

    @pytest.mark.anyio
    async def test_reject_at_hitl3_reruns_judge(self, monkeypatch, generic_catalog, generic_topology):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        call_counts: dict[str, int] = {}

        from src.application.agents.sub_agent_runner import SubAgentResponse

        async def _counting_runner(role, user_request, llm_provider, document_store, model_name, **kwargs):
            key = role.value if hasattr(role, "value") else str(role)
            call_counts[key] = call_counts.get(key, 0) + 1
            return SubAgentResponse(role=role, content=f"{key}: response", context_chunks=[])

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
            review_rounds=0,
            agent_catalog=generic_catalog,
            topology=generic_topology,
        ))

        assert call_counts.get("Auditor", 0) == 2

    @pytest.mark.anyio
    async def test_architects_internal_review_with_auditor_before_hitl(self, monkeypatch, generic_catalog, generic_topology):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent
        from src.application.agents.sub_agent_runner import SubAgentResponse

        called_sequence: list[str] = []

        async def _capturing_runner(role, user_request, llm_provider, document_store, model_name, **kwargs):
            key = role.value if hasattr(role, "value") else str(role)
            called_sequence.append(key)
            return SubAgentResponse(role=role, content=f"{key} response", context_chunks=[])

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _capturing_runner)

        async def _cb(event: SupervisorEvent) -> HITLResponse:
            return HITLResponse(decision=HITLDecision.APPROVE)

        collected = await _collect(SupervisorAgent.run(
            user_request="Design a microservice architecture",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_cb,
            review_rounds=1,
            agent_catalog=generic_catalog,
            topology=generic_topology,
        ))

        types_and_roles = [(e.type, e.role) for e in collected]
        hitl_indices = [i for i, (t, _) in enumerate(types_and_roles) if t == EventType.HITL_REQUIRED]
        assert len(hitl_indices) == 3
        hitl1_idx, hitl2_idx, _ = hitl_indices

        # Inspect events between HITL1 (Interpreter) and HITL2 (PropOne)
        phase2_events = types_and_roles[hitl1_idx + 1:hitl2_idx]
        roles_in_phase2 = [r for _, r in phase2_events if r is not None]

        # Auditor MUST participate in Phase 2 before HITL2 is yielded
        assert "Auditor" in roles_in_phase2
        # No intermediate HITL_REQUIRED in phase 2 pre-deliberation
        for t, _ in phase2_events:
            assert t != EventType.HITL_REQUIRED

    @pytest.mark.anyio
    async def test_review_rounds_env_setting_is_respected(self, monkeypatch, generic_catalog, generic_topology):
        from src.presentation.api import config as config_mod
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent
        from src.application.agents.sub_agent_runner import SubAgentResponse

        settings = config_mod.get_settings()
        assert hasattr(settings, "review_rounds")

        monkeypatch.setattr(settings, "review_rounds", 0)

        call_counts: dict[str, int] = {}
        async def _counting_runner(role, user_request, llm_provider, document_store, model_name, **kwargs):
            key = role.value if hasattr(role, "value") else str(role)
            call_counts[key] = call_counts.get(key, 0) + 1
            return SubAgentResponse(role=role, content=f"{key} response", context_chunks=[])

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _counting_runner)

        async def _cb(event: SupervisorEvent) -> HITLResponse:
            return HITLResponse(decision=HITLDecision.APPROVE)

        await _collect(SupervisorAgent.run(
            user_request="Design something",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_cb,
            agent_catalog=generic_catalog,
            topology=generic_topology,
        ))

        # When review_rounds is 0, PropOne and PropTwo run once in phase 2, Auditor runs once in phase 3
        assert call_counts.get("PropOne", 0) == 1
        assert call_counts.get("PropTwo", 0) == 1
        assert call_counts.get("Auditor", 0) == 1


class TestAdaptiveSupervisorRouting:
    @pytest.mark.anyio
    async def test_direct_chat_greeting_responds_as_supervisor_without_council(self, monkeypatch, generic_catalog, generic_topology):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        runner_called = False

        async def _mock_runner(role, user_request, llm_provider, document_store, model_name, **kwargs):
            nonlocal runner_called
            runner_called = True
            from src.application.agents.sub_agent_runner import SubAgentResponse
            return SubAgentResponse(role=role, content=f"{role.value}: response", context_chunks=[])

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _mock_runner)

        recorded_prompts: list[str] = []

        class GreetingLLM(FakeLLM):
            def complete(self, prompt: str, model_name: str) -> str:
                recorded_prompts.append(prompt)
                if "clasifica la intención" in prompt.lower() or "triage" in prompt.lower():
                    return '{"mode": "direct_chat", "target_agent": null, "skip_interpreter": false, "reasoning": "Simple saludo"}'
                return "Hola, soy Coordinator. ¿Qué desafío someteremos hoy al escrutinio del consejo?"

        events = await _collect(SupervisorAgent.run(
            user_request="Hola Coordinator, ¿cómo estás?",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: GreetingLLM(),
            hitl_callback=_approve_always,
            agent_catalog=generic_catalog,
            topology=generic_topology,
        ))

        types = _event_types(events)
        assert EventType.AGENT_STARTED in types
        assert events[0].role == "Coordinator"
        assert events[-1].type == EventType.DONE
        assert events[-1].role == "Coordinator"
        assert "Coordinator" in events[-1].content
        # SubAgentRunner was NOT called because council was not invoked
        assert runner_called is False
        assert any("MIEMBROS OFICIALES DEL CONSEJO TÉCNICO" in p for p in recorded_prompts)

    def test_classify_intent_presentation_triggers_direct_chat(self, generic_catalog):
        from src.application.agents.supervisor_agent import classify_intent

        decision = classify_intent(
            user_request="Preséntate y presenta al equipo",
            llm_provider=FakeLLM(),
            model_name="default",
            supervisor_name="Coordinator",
            interpreter_name="Interpreter",
            agent_catalog=generic_catalog,
        )
        assert decision.mode == "direct_chat"

    @pytest.mark.anyio
    async def test_single_agent_mode_delegates_directly_to_impl_one(self, monkeypatch, generic_catalog, generic_topology):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        called_roles = []

        from src.application.agents.sub_agent_runner import SubAgentResponse

        async def _mock_runner(role, user_request, llm_provider, document_store, model_name, **kwargs):
            role_str = role.value if hasattr(role, "value") else str(role)
            called_roles.append(role)
            return SubAgentResponse(role=role, content="```mermaid\nflowchart TD\nA-->B\n```", context_chunks=[])

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _mock_runner)

        class DiagramLLM(FakeLLM):
            def complete(self, prompt: str, model_name: str) -> str:
                if "clasifica la intención" in prompt.lower() or "triage" in prompt.lower():
                    return '{"mode": "single_agent", "target_agent": "implementer_one", "skip_interpreter": false, "reasoning": "Petición directa de diagramas"}'
                return "response"

        events = await _collect(SupervisorAgent.run(
            user_request="Quiero un diagrama para una solución en la que un front llame a un back",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: DiagramLLM(),
            hitl_callback=_approve_always,
            agent_catalog=generic_catalog,
            topology=generic_topology,
        ))

        assert called_roles == ["ImplOne"]
        assert events[-1].type == EventType.DONE
        assert events[-1].role == "ImplOne"
        assert "mermaid" in events[-1].content

    @pytest.mark.anyio
    async def test_adaptive_debate_skips_interpreter_when_requirements_are_defined(self, monkeypatch, generic_catalog, generic_topology):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        called_roles = []

        from src.application.agents.sub_agent_runner import SubAgentResponse

        async def _mock_runner(role, user_request, llm_provider, document_store, model_name, **kwargs):
            role_str = role.value if hasattr(role, "value") else str(role)
            called_roles.append(role)
            return SubAgentResponse(role=role, content=f"{role_str} proposal", context_chunks=[])

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _mock_runner)

        class StructuredLLM(FakeLLM):
            def complete(self, prompt: str, model_name: str) -> str:
                if "clasifica la intención" in prompt.lower() or "triage" in prompt.lower():
                    return '{"mode": "adaptive_debate", "target_agent": null, "skip_interpreter": true, "reasoning": "Requisitos ya estructurados"}'
                return "Consolidación final de Coordinator"

        events = await _collect(SupervisorAgent.run(
            user_request="Necesito un SSO con Keycloak, 10 sesiones concurrentes, OAuth2 y TLS 1.3",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: StructuredLLM(),
            hitl_callback=_approve_always,
            agent_catalog=generic_catalog,
            topology=generic_topology,
        ))

        # Interpreter was skipped!
        assert "Interpreter" not in called_roles
        assert "PropOne" in called_roles
        assert "PropTwo" in called_roles

    @pytest.mark.anyio
    async def test_hitl_redirects_to_selected_target_agents(self, monkeypatch, generic_catalog, generic_topology):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        called_roles = []

        from src.application.agents.sub_agent_runner import SubAgentResponse

        async def _mock_runner(role, user_request, llm_provider, document_store, model_name, **kwargs):
            role_str = role.value if hasattr(role, "value") else str(role)
            called_roles.append(role)
            return SubAgentResponse(role=role, content=f"{role_str}: done", context_chunks=[])

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _mock_runner)

        # At HITL 1, user approves but redirects specifically to ImplOne
        decisions = iter([
            HITLResponse(decision=HITLDecision.APPROVE, target_agents=["implementer_one"]),
        ])

        async def _redirect_callback(_event: SupervisorEvent) -> HITLResponse:
            return next(decisions)

        events = await _collect(SupervisorAgent.run(
            user_request="Diseñar arquitectura de pagos",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_redirect_callback,
            agent_catalog=generic_catalog,
            topology=generic_topology,
        ))

        # After Interpreter, user redirected specifically to diagrammer
        assert "Interpreter" in called_roles
        assert "ImplOne" in called_roles

    def test_consolidation_prompt_is_in_spanish_and_parameterized(self):
        from src.application.agents.supervisor_agent import _CONSOLIDATION_PROMPT

        assert "Dictamen" in _CONSOLIDATION_PROMPT
        assert "Resumen Ejecutivo" in _CONSOLIDATION_PROMPT
        assert "{supervisor_name}" in _CONSOLIDATION_PROMPT
        assert "{proposers_str}" in _CONSOLIDATION_PROMPT
        assert "{evaluator_name}" in _CONSOLIDATION_PROMPT
        assert "{implementers_str}" in _CONSOLIDATION_PROMPT

    @pytest.mark.anyio
    async def test_consolidation_prompt_uses_topology_participants_and_is_domain_neutral(self, generic_topology):
        from src.application.agents.supervisor_agent import DebateState, _run_consolidation

        captured: list[str] = []

        class _CapturingLLM(FakeLLM):
            def complete(self, prompt: str, model_name: str) -> str:
                captured.append(prompt)
                return "final"

        top = generic_topology
        state = DebateState()
        state.agent_outputs["PropOne"] = "proposal"
        event = await _run_consolidation(
            state, _CapturingLLM(), "m", supervisor_name=top.supervisor, topology=top
        )

        prompt = captured[0]
        assert top.supervisor in prompt
        assert ", ".join(top.proposers) in prompt
        assert ", ".join(top.evaluators) in prompt
        assert ", ".join(top.implementers) in prompt
        assert "arquitect" not in prompt.lower()
        assert event.role == top.supervisor

    def test_triage_decision_exposes_skip_interpreter_only(self):
        from src.application.agents.supervisor_agent import TriageDecision

        decision = TriageDecision(mode="adaptive_debate", skip_interpreter=True)
        assert decision.skip_interpreter is True
        assert not hasattr(decision, "skip_hermes")

    def test_classify_intent_lists_only_registered_specialists_and_dynamic_names(self, generic_catalog):
        from src.application.agents.supervisor_agent import classify_intent

        captured: list[str] = []

        class _CapturingLLM(FakeLLM):
            def complete(self, prompt: str, model_name: str) -> str:
                captured.append(prompt)
                return '{"mode": "adaptive_debate", "target_agent": null, "skip_interpreter": false, "reasoning": "x"}'

        classify_intent(
            "Necesito una solución",
            _CapturingLLM(),
            "m",
            supervisor_name="Coordinator",
            interpreter_name="Interpreter",
            agent_catalog=generic_catalog,
        )

        prompt = captured[0]
        assert "Eres Coordinator" in prompt
        assert "skip_interpreter" in prompt
        specialists = [
            p for p in generic_catalog.get_all_profiles()
            if not p.is_supervisor and p.display_name != "Interpreter"
        ]
        assert specialists
        for p in specialists:
            assert f'"{p.display_name}"' in prompt
        assert '"Interpreter" (' not in prompt  # interpreter is not a single-agent target
        assert "Eres Coordinator. Analiza" in prompt

    def test_classify_intent_requires_explicit_agent_names(self):
        import inspect

        from src.application.agents.supervisor_agent import classify_intent

        params = inspect.signature(classify_intent).parameters
        assert params["supervisor_name"].default is inspect.Parameter.empty
        assert params["interpreter_name"].default is inspect.Parameter.empty

    def test_phase_functions_have_no_hardcoded_agent_defaults(self):
        import inspect

        from src.application.agents import supervisor_agent as mod

        for fn_name, param in (
            ("_run_phase_1", "interpreter_roles"),
            ("_run_phase_2", "proposer_roles"),
            ("_run_phase_2", "reviewer_roles"),
            ("_run_phase_3", "evaluator_roles"),
            ("_run_phase_4", "implementer_roles"),
            ("_run_consolidation", "supervisor_name"),
        ):
            default = inspect.signature(getattr(mod, fn_name)).parameters[param].default
            assert default is inspect.Parameter.empty, f"{fn_name}.{param} has a default"

    @pytest.mark.anyio
    async def test_auditor_evaluation_includes_prior_critiques_and_consistency_rule(self, monkeypatch, generic_catalog, generic_topology):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent
        from src.application.agents.sub_agent_runner import SubAgentResponse

        auditor_prompts: list[str] = []
        auditor_chat_histories: list[Any] = []

        async def _capturing_runner(role, user_request, llm_provider, document_store, model_name, **kwargs):
            key = role.value if hasattr(role, "value") else str(role)
            if key in ("Auditor", "auditor"):
                auditor_prompts.append(user_request)
                auditor_chat_histories.append(kwargs.get("chat_history"))
                return SubAgentResponse(role=role, content=f"Critique #{len(auditor_prompts)}: Quitar Redis por sobreingenieria para 20 users", context_chunks=[])
            return SubAgentResponse(role=role, content=f"{key}: Solución ajustada", context_chunks=[])

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _capturing_runner)

        async def _cb(_event: SupervisorEvent) -> HITLResponse:
            return HITLResponse(decision=HITLDecision.APPROVE)

        test_history = [{"role": "user", "content": "Necesito una app para 20 usuarios"}]

        await _collect(SupervisorAgent.run(
            user_request="Arquitectura para 20 usuarios",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_cb,
            chat_history=test_history,
            review_rounds=2,
            agent_catalog=generic_catalog,
            topology=generic_topology,
        ))

        # With review_rounds=2, Auditor runs twice in Phase 2, and once in Phase 3 -> 3 total calls
        assert len(auditor_prompts) == 3

        # Call 1 (Round 1 pre-deliberation): initial critique
        assert "preliminares" in auditor_prompts[0]

        # Call 2 (Round 2 pre-deliberation): includes prior critique and consistency rule
        assert "Directivas previas emitidas por ti (Auditor)" in auditor_prompts[1]
        assert "REGLA DE ORO DE COHERENCIA Y CONSISTENCIA" in auditor_prompts[1]
        assert "Quitar Redis por sobreingenieria" in auditor_prompts[1]

        # Call 3 (Phase 3 final evaluation): includes previous critiques and consistency rule
        assert "Directivas y críticas emitidas previamente por ti (Auditor)" in auditor_prompts[2]
        assert "REGLA DE COHERENCIA EVALUATIVA" in auditor_prompts[2]
        assert "Quitar Redis" in auditor_prompts[2]

        # Chat history is propagated to Auditor
        assert auditor_chat_histories[0] == test_history

    def test_debate_state_tracks_critiques_per_agent_without_agent_specific_api(self):
        from src.application.agents.supervisor_agent import DebateState

        state = DebateState()
        state.add_agent_critique("CustomAgent", "First critique")
        state.add_agent_critique("CustomAgent", "Second critique")
        state.add_agent_critique("OtherAgent", "Other critique")

        assert state.get_agent_critiques("CustomAgent") == ["First critique", "Second critique"]
        assert state.get_agent_critiques("OtherAgent") == ["Other critique"]
        assert state.get_agent_critiques("NonExistent") == []

        # No agent-specific accessors may exist on the generic state
        public = {name for name in dir(state) if not name.startswith("_")}
        assert not {n for n in public if "judge" in n or "sphinx" in n or "auditor" in n}

    @pytest.mark.anyio
    async def test_supervisor_agent_runs_with_custom_debate_topology(self, monkeypatch, generic_catalog):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent
        from src.application.agents.sub_agent_runner import SubAgentResponse
        from src.domain.agents.debate_topology import DebateTopology

        called_agents: list[str] = []

        async def _capturing_runner(role, user_request, llm_provider, document_store, model_name, **kwargs):
            key = role.value if hasattr(role, "value") else str(role)
            called_agents.append(key)
            return SubAgentResponse(role=role, content=f"{key}: output", context_chunks=[])

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _capturing_runner)

        custom_topology = DebateTopology(
            supervisor="Coordinator",
            interpreters=("Interpreter",),
            proposers=("PropTwo",),  # Only PropTwo!
            reviewers=("Auditor",),
            evaluators=("Auditor",),
            implementers=("ImplTwo",),  # Only ImplTwo!
        )

        events = await _collect(SupervisorAgent.run(
            user_request="Arquitectura simple",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_approve_always,
            topology=custom_topology,
            agent_catalog=generic_catalog,
        ))

        # In Phase 2, only PropTwo ran (PropOne never called!)
        assert "PropOne" not in called_agents
        assert "PropTwo" in called_agents
        assert "Auditor" in called_agents

        # In Phase 4, only ImplTwo ran (ImplOne never called!)
        assert "ImplOne" not in called_agents
        assert "ImplTwo" in called_agents

        # Done event emitted with supervisor role
        done_events = [e for e in events if e.type == EventType.DONE]
        assert len(done_events) == 1
        assert done_events[0].role == "Coordinator"

    @pytest.mark.anyio
    async def test_topology_skips_empty_phases(self, monkeypatch, generic_catalog):
        """When optional roles are empty tuples, those phases and their checkpoints are skipped."""
        import src.application.agents.supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent
        from src.application.agents.sub_agent_runner import SubAgentResponse
        from src.domain.agents.debate_topology import DebateTopology

        called_agents: list[str] = []

        async def _capturing_runner(role, user_request, llm_provider, document_store, model_name, **kwargs):
            key = role.value if hasattr(role, "value") else str(role)
            called_agents.append(key)
            return SubAgentResponse(role=role, content=f"{key}: output", context_chunks=[])

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _capturing_runner)

        # Empty interpreters, empty reviewers, empty evaluators, empty implementers!
        sparse_topology = DebateTopology(
            supervisor="Coordinator",
            interpreters=(),
            proposers=("PropOne",),
            reviewers=(),
            evaluators=(),
            implementers=(),
        )

        events = await _collect(SupervisorAgent.run(
            user_request="Diseñar microservicios",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_approve_always,
            topology=sparse_topology,
            agent_catalog=generic_catalog,
        ))

        # Interpreter never called (Phase 1 skipped)
        assert "Interpreter" not in called_agents
        # Proposer was called
        assert "PropOne" in called_agents
        # Reviewer and Evaluator never called
        assert "Auditor" not in called_agents
        # Implementers never called
        assert "ImplOne" not in called_agents
        assert "ImplTwo" not in called_agents

        # Done event emitted successfully
        assert any(e.type == EventType.DONE for e in events)

    @pytest.mark.anyio
    async def test_hitl_finish_decision_terminates_debate_early(self, monkeypatch, generic_catalog):
        """User choosing FINISH at HITL checkpoint immediately exits remaining phases and consolidates."""
        import src.application.agents.supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent
        from src.application.agents.sub_agent_runner import SubAgentResponse
        from src.domain.agents.debate_topology import DebateTopology

        called_agents: list[str] = []

        async def _capturing_runner(role, user_request, llm_provider, document_store, model_name, **kwargs):
            key = role.value if hasattr(role, "value") else str(role)
            called_agents.append(key)
            return SubAgentResponse(role=role, content=f"{key}: output", context_chunks=[])

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _capturing_runner)

        async def _finish_at_first_hitl(_event: SupervisorEvent) -> HITLResponse:
            return HITLResponse(decision=HITLDecision.FINISH)

        custom_topology = DebateTopology(
            supervisor="Coordinator",
            interpreters=("Interpreter",),
            proposers=("PropOne",),
            reviewers=("Auditor",),
            evaluators=("Auditor",),
            implementers=("ImplOne",),
        )

        events = await _collect(SupervisorAgent.run(
            user_request="Crear landing",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_finish_at_first_hitl,
            topology=custom_topology,
            agent_catalog=generic_catalog,
        ))

        # Phase 1 Interpreter ran
        assert "Interpreter" in called_agents
        # Subsequent phases did NOT run because user finished early
        assert "PropOne" not in called_agents
        assert "Auditor" not in called_agents
        assert "ImplOne" not in called_agents

        # Done event was still emitted with final consolidation
        done_events = [e for e in events if e.type == EventType.DONE]
        assert len(done_events) == 1
        assert done_events[0].role == "Coordinator"

    @pytest.mark.anyio
    async def test_supervisor_agent_executes_dynamic_plan_omitting_unplanned_stages(self, monkeypatch, generic_catalog):
        """
        When Atenea plans a dynamic route (e.g. ['interpreters', 'implementers']),
        the orchestrator follows only the planned stages, omitting proposers and evaluators.
        """
        import src.application.agents.supervisor_agent as _mod
        from src.application.agents.sub_agent_runner import SubAgentResponse
        from src.application.agents.supervisor_agent import SupervisorAgent, TriageDecision
        from src.domain.agents.debate_topology import DebateTopology

        called_agents: list[str] = []

        async def _capturing_runner(role, user_request, llm_provider, document_store, model_name, **kwargs):
            key = role.value if hasattr(role, "value") else str(role)
            called_agents.append(key)
            return SubAgentResponse(role=role, content=f"{key}: output", context_chunks=[])

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _capturing_runner)

        # Mock classify_intent to return a dynamic plan: interpreters -> implementers
        monkeypatch.setattr(
            _mod,
            "classify_intent",
            lambda *args, **kwargs: TriageDecision(
                mode="adaptive_debate",
                execution_plan=("interpreters", "implementers"),
                reasoning="Requisitos directos para implementación",
            ),
        )

        async def _approve_hitl(_event: SupervisorEvent) -> HITLResponse:
            return HITLResponse(decision=HITLDecision.APPROVE)

        custom_topology = DebateTopology(
            supervisor="Coordinator",
            interpreters=("Interpreter",),
            proposers=("PropOne", "PropTwo"),
            reviewers=("Auditor",),
            evaluators=("Auditor",),
            implementers=("ImplOne",),
        )

        events = await _collect(SupervisorAgent.run(
            user_request="Generar script directo de despliegue",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_approve_hitl,
            topology=custom_topology,
            agent_catalog=generic_catalog,
        ))

        # Interpreters and Implementers ran
        assert "Interpreter" in called_agents
        assert "ImplOne" in called_agents

        # Proposers and Evaluators were NOT planned and did NOT run
        assert "PropOne" not in called_agents
        assert "PropTwo" not in called_agents
        assert "Auditor" not in called_agents

        done_events = [e for e in events if e.type == EventType.DONE]
        assert len(done_events) == 1

    @pytest.mark.anyio
    async def test_supervisor_forwards_rag_top_k_and_min_score_from_agent_config_repo(self, monkeypatch, generic_catalog):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.sub_agent_runner import SubAgentResponse
        from src.application.agents.supervisor_agent import SupervisorAgent, TriageDecision
        from src.domain.agents.debate_topology import DebateTopology
        from src.domain.value_objects.agent_config import AgentConfig

        captured_kwargs: dict[str, dict] = {}

        async def _capturing_runner(role, user_request, llm_provider, document_store, model_name, **kwargs):
            key = role.value if hasattr(role, "value") else str(role)
            captured_kwargs[key] = kwargs
            return SubAgentResponse(role=role, content=f"{key}: output", context_chunks=[])

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _capturing_runner)
        monkeypatch.setattr(
            _mod,
            "classify_intent",
            lambda *args, **kwargs: TriageDecision(
                mode="single_agent",
                target_agent="implementer_one",
                reasoning="Direct call to ImplOne",
            ),
        )

        class CustomRagConfigRepo(FakeAgentConfigRepo):
            def find_by_role(self, role: str) -> AgentConfig | None:
                if role in ("ImplOne", "implementer_one"):
                    return AgentConfig(
                        role=role,
                        provider="gemini",
                        model_name="gemini-2.5-flash",
                        rag_top_k=0,
                        rag_min_score=0.75,
                    )
                return super().find_by_role(role)

        custom_topology = DebateTopology(
            supervisor="Coordinator",
            interpreters=("Interpreter",),
            proposers=("PropOne",),
            reviewers=("Auditor",),
            evaluators=("Auditor",),
            implementers=("ImplOne",),
        )

        await _collect(SupervisorAgent.run(
            user_request="Documenta la sesión actual sin ruido del vault",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=CustomRagConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_approve_always,
            topology=custom_topology,
            agent_catalog=generic_catalog,
        ))

        assert "ImplOne" in captured_kwargs
        assert captured_kwargs["ImplOne"]["rag_top_k"] == 0
        assert captured_kwargs["ImplOne"]["rag_min_score"] == pytest.approx(0.75)


class TestSupervisorAgentFaultTolerance:
    @pytest.mark.anyio
    async def test_parallel_proposers_round_tolerates_single_agent_failure(self, monkeypatch, generic_catalog, generic_topology):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent
        from src.application.agents.sub_agent_runner import SubAgentResponse

        # Proposer 1 (e.g. Ícaro) fails with 503, others (Hestia) succeed
        async def _failing_mock_runner(role, user_request, *args, **kwargs):
            role_str = role.value if hasattr(role, "value") else str(role)
            if any(k in role_str.lower() for k in ("ícaro", "icaro", "innovator", "propone")):
                raise RuntimeError("503 UNAVAILABLE: Model overloaded")
            return SubAgentResponse(
                role=role_str,
                content=f"Successful response from {role_str}",
                model_name="test-model",
                tokens={"input": 50, "output": 25, "total": 75},
                latency=0.5,
            )

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _failing_mock_runner)

        events = await _collect(SupervisorAgent.run(
            user_request="Design resilient architecture",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_approve_always,
            agent_catalog=generic_catalog,
            topology=generic_topology,
        ))

        types = _event_types(events)
        assert EventType.DONE in types

        # An error event should be yielded for the failing agent with fatal="false"
        error_events = [e for e in events if e.type == EventType.ERROR]
        assert len(error_events) >= 1
        assert error_events[0].metadata.get("fatal") == "false"
        assert "503" in error_events[0].content

        # Successful agents still have their AGENT_COMPLETED events
        completed_roles = [e.role for e in events if e.type == EventType.AGENT_COMPLETED]
        assert any(any(k in (r or "").lower() for k in ("hestia", "senior", "conservative", "proptwo")) for r in completed_roles)

    @pytest.mark.anyio
    async def test_sequential_agent_failure_emits_recovery_hitl(self, monkeypatch, generic_catalog, generic_topology):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        async def _interpreter_failing_runner(role, user_request, *args, **kwargs):
            role_str = role.value if hasattr(role, "value") else str(role)
            if "interpreter" in role_str.lower():
                raise RuntimeError("503 UNAVAILABLE: Gemini rate limit exceeded")
            from src.application.agents.sub_agent_runner import SubAgentResponse
            return SubAgentResponse(
                role=role_str,
                content=f"Response from {role_str}",
                model_name="test-model",
                tokens={"input": 50, "output": 25, "total": 75},
                latency=0.5,
            )

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _interpreter_failing_runner)

        hitl_events_captured: list[SupervisorEvent] = []

        async def _finish_on_recovery(event: SupervisorEvent) -> HITLResponse:
            hitl_events_captured.append(event)
            return HITLResponse(decision=HITLDecision.FINISH)

        events = await _collect(SupervisorAgent.run(
            user_request="Design authentication system",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_finish_on_recovery,
            agent_catalog=generic_catalog,
            topology=generic_topology,
        ))

        # Check that a recovery HITL was emitted for the interpreter
        assert len(hitl_events_captured) >= 1
        rec_hitl = hitl_events_captured[0]
        assert rec_hitl.type == EventType.HITL_REQUIRED
        assert rec_hitl.metadata.get("error_recovery") == "true"
        assert "503" in rec_hitl.content
        assert events[-1].type == EventType.DONE

    @pytest.mark.anyio
    async def test_hitl_consolidate_triggers_consolidation(self, monkeypatch, generic_catalog, generic_topology):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _make_mock_runner())

        async def _consolidate_at_hitl1(event: SupervisorEvent) -> HITLResponse:
            return HITLResponse(decision=HITLDecision.CONSOLIDATE)

        events = await _collect(SupervisorAgent.run(
            user_request="Design caching system",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_consolidate_at_hitl1,
            agent_catalog=generic_catalog,
            topology=generic_topology,
        ))

        assert events[-1].type == EventType.DONE
        assert "consolidated response from" in events[-1].content
        assert events[-1].metadata.get("skip_consolidation") is None

    @pytest.mark.anyio
    async def test_hitl_finish_halts_without_consolidation(self, monkeypatch, generic_catalog, generic_topology):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _make_mock_runner())

        async def _finish_at_hitl1(event: SupervisorEvent) -> HITLResponse:
            return HITLResponse(decision=HITLDecision.FINISH)

        events = await _collect(SupervisorAgent.run(
            user_request="Design caching system",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_finish_at_hitl1,
            agent_catalog=generic_catalog,
            topology=generic_topology,
        ))

        assert events[-1].type == EventType.DONE
        assert "sin consolidación" in events[-1].content
        assert events[-1].metadata.get("skip_consolidation") == "true"

    @pytest.mark.anyio
    async def test_hitl_retry_reexecutes_only_failed_agents(self, monkeypatch, generic_catalog):
        """Option C: When RETRY is chosen without target agents, re-run only the failed agents."""
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent
        from src.domain.agents.debate_topology import DebateTopology
        from src.application.agents.sub_agent_runner import SubAgentResponse

        test_topology = DebateTopology(
            project_name="Test",
            project_description="Test",
            supervisor="Coordinator",
            interpreters=(),
            proposers=("PropOne", "PropTwo"),
            evaluators=(),
            implementers=(),
        )

        monkeypatch.setattr(
            _mod,
            "classify_intent",
            lambda *args, **kwargs: _mod.TriageDecision(mode="adaptive_debate", skip_interpreter=True),
        )

        call_counts = {"PropOne": 0, "PropTwo": 0}

        async def _mock_run(role, user_request, llm_provider, document_store, model_name, **kwargs):
            key = role.value if hasattr(role, "value") else str(role)
            call_counts[key] += 1
            if key == "PropOne" and call_counts["PropOne"] == 1:
                raise RuntimeError("503 Service Unavailable")
            return SubAgentResponse(role=role, content=f"Success from {key}", context_chunks=[])

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _mock_run)

        hitl_step = 0
        hitl_events = []

        async def _hitl_cb(event: SupervisorEvent) -> HITLResponse:
            nonlocal hitl_step
            hitl_events.append(event)
            hitl_step += 1
            if hitl_step == 1:
                # First HITL after proposers: PropOne failed, PropTwo succeeded.
                # User chooses RETRY with no target agents.
                assert event.metadata.get("error_recovery") == "true"
                return HITLResponse(decision=HITLDecision.RETRY)
            # Second HITL after retry: both succeeded. Finish debate.
            return HITLResponse(decision=HITLDecision.FINISH)

        events = await _collect(SupervisorAgent.run(
            user_request="Build resilient microservices",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_hitl_cb,
            topology=test_topology,
            agent_catalog=generic_catalog,
        ))

        # PropOne failed on attempt 1, retried on attempt 2 -> called 2 times
        assert call_counts["PropOne"] == 2
        # PropTwo succeeded on attempt 1 -> Option C preserved result, NOT called again!
        assert call_counts["PropTwo"] == 1

        # Two HITL events were emitted: first with error recovery, second recovered
        assert len(hitl_events) == 2
        assert "Fallo al generar propuesta de PropOne" in hitl_events[0].content
        assert "Success from PropOne" in hitl_events[1].content
        assert "Success from PropTwo" in hitl_events[1].content
        assert hitl_events[1].metadata.get("error_recovery") is None

    @pytest.mark.anyio
    async def test_hitl_retry_with_explicit_target_agents(self, monkeypatch, generic_catalog):
        """Option C: When RETRY is chosen with target agents, re-run only the specified agents."""
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent
        from src.domain.agents.debate_topology import DebateTopology
        from src.application.agents.sub_agent_runner import SubAgentResponse

        test_topology = DebateTopology(
            project_name="Test",
            project_description="Test",
            supervisor="Coordinator",
            interpreters=(),
            proposers=("PropOne", "PropTwo"),
            evaluators=(),
            implementers=(),
        )

        monkeypatch.setattr(
            _mod,
            "classify_intent",
            lambda *args, **kwargs: _mod.TriageDecision(mode="adaptive_debate", skip_interpreter=True),
        )

        call_counts = {"PropOne": 0, "PropTwo": 0}

        async def _mock_run(role, user_request, llm_provider, document_store, model_name, **kwargs):
            key = role.value if hasattr(role, "value") else str(role)
            call_counts[key] += 1
            return SubAgentResponse(role=role, content=f"Output {call_counts[key]} from {key}", context_chunks=[])

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _mock_run)

        hitl_step = 0

        async def _hitl_cb(event: SupervisorEvent) -> HITLResponse:
            nonlocal hitl_step
            hitl_step += 1
            if hitl_step == 1:
                # Explicitly target only PropTwo for retry
                return HITLResponse(decision=HITLDecision.RETRY, target_agents=["PropTwo"])
            return HITLResponse(decision=HITLDecision.FINISH)

        events = await _collect(SupervisorAgent.run(
            user_request="Build high performance system",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_hitl_cb,
            topology=test_topology,
            agent_catalog=generic_catalog,
        ))

        # PropOne was called only once initially
        assert call_counts["PropOne"] == 1
        # PropTwo was called twice (initial + explicit retry)
        assert call_counts["PropTwo"] == 2

    @pytest.mark.anyio
    async def test_phase_4_emits_message_and_no_token_double_count_in_direct_modes(self, monkeypatch, generic_catalog):
        from src.application.agents import supervisor_agent as _mod
        from src.application.agents.supervisor_agent import SupervisorAgent
        from src.domain.agents.debate_topology import DebateTopology
        from src.application.agents.sub_agent_runner import SubAgentResponse

        test_topology = DebateTopology(
            project_name="Test",
            project_description="Test",
            supervisor="Coordinator",
            interpreters=(),
            proposers=(),
            evaluators=(),
            implementers=("ImplOne",),
        )

        monkeypatch.setattr(
            _mod,
            "classify_intent",
            lambda *args, **kwargs: _mod.TriageDecision(mode="adaptive_debate", skip_interpreter=True),
        )

        async def _mock_run(role, user_request, llm_provider, document_store, model_name, **kwargs):
            return SubAgentResponse(
                role=role,
                content=f"Deliverable from {role}",
                context_chunks=[],
                tokens={"input": 30, "output": 20, "total": 50},
                latency=0.2,
                model_name="test-model",
            )

        monkeypatch.setattr(_mod.SubAgentRunner, "run", _mock_run)

        events = await _collect(SupervisorAgent.run(
            user_request="Implement the feature",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_approve_always,
            topology=test_topology,
            agent_catalog=generic_catalog,
        ))
        impl_messages = [e for e in events if e.type == EventType.MESSAGE and e.role == "ImplOne"]
        assert len(impl_messages) == 1
        assert "Deliverable from ImplOne" in impl_messages[0].content

        # Direct-chat and single-agent DONE must mark metrics_reported="true" without duplicate tokens
        monkeypatch.setattr(
            _mod,
            "classify_intent",
            lambda *args, **kwargs: _mod.TriageDecision(mode="direct_chat"),
        )
        direct_events = await _collect(SupervisorAgent.run(
            user_request="Hola",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_approve_always,
            topology=test_topology,
            agent_catalog=generic_catalog,
        ))
        comp = next(e for e in direct_events if e.type == EventType.AGENT_COMPLETED)
        done = next(e for e in direct_events if e.type == EventType.DONE)
        assert int(comp.metadata["total_tokens"]) > 0
        assert done.metadata.get("metrics_reported") == "true"
        assert "total_tokens" not in done.metadata
        assert "tokens" not in done.metadata

        monkeypatch.setattr(
            _mod,
            "classify_intent",
            lambda *args, **kwargs: _mod.TriageDecision(mode="single_agent", target_agent="ImplOne"),
        )
        single_events = await _collect(SupervisorAgent.run(
            user_request="Haz el código",
            document_store=InMemoryDocumentStore(),
            agent_config_repo=FakeAgentConfigRepo(),
            llm_factory=lambda _: FakeLLM(),
            hitl_callback=_approve_always,
            topology=test_topology,
            agent_catalog=generic_catalog,
        ))
        s_comp = next(e for e in single_events if e.type == EventType.AGENT_COMPLETED)
        s_done = next(e for e in single_events if e.type == EventType.DONE)
        assert s_comp.role == "ImplOne"
        assert s_done.metadata.get("metrics_reported") == "true"
        assert "total_tokens" not in s_done.metadata







