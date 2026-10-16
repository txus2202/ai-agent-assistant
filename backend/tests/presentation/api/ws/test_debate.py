"""
Tests — Debate WebSocket Endpoint (feature_websocket_debate.md)

Layer: Presentation

Strategy:
  - Use FastAPI's TestClient for synchronous WebSocket testing
  - Mock SupervisorAgent.run() to yield a predictable sequence of events
  - Verify JSON serialization and HITL blocking mechanics
  - Test validation and error handling on initial connection
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.domain.agents.sub_agent_profiles import AgentRole
from src.domain.agents.supervisor_events import (
    EventType,
    HITLDecision,
    SupervisorEvent,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

async def _fake_debate_generator(*args, **kwargs):
    """
    Mocks SupervisorAgent.run to yield:
      1. AGENT_STARTED (NL_INTERPRETER)
      2. HITL_REQUIRED (1_interpreter)
      3. HITL_REQUIRED (2_architects)
      4. HITL_REQUIRED (3_judge)
      5. DONE
    """
    hitl_callback = kwargs.get("hitl_callback")
    
    # Event 1
    yield SupervisorEvent(
        type=EventType.AGENT_STARTED,
        role=AgentRole.NL_INTERPRETER,
        content="starting"
    )
    
    # Event 2: HITL 1
    hitl1_event = SupervisorEvent(
        type=EventType.HITL_REQUIRED,
        role=None,
        content="Please review interpretation",
        metadata={"checkpoint": "1_interpreter"}
    )
    yield hitl1_event
    hitl1_resp = await hitl_callback(hitl1_event)
    
    # Event 3: HITL 2
    hitl2_event = SupervisorEvent(
        type=EventType.HITL_REQUIRED,
        role=None,
        content="Please review architects",
        metadata={"checkpoint": "2_architects"}
    )
    yield hitl2_event
    hitl2_resp = await hitl_callback(hitl2_event)

    # Event 4: HITL 3
    hitl3_event = SupervisorEvent(
        type=EventType.HITL_REQUIRED,
        role=None,
        content="Please review judge",
        metadata={"checkpoint": "3_judge"}
    )
    yield hitl3_event
    hitl3_resp = await hitl_callback(hitl3_event)
    
    # Event 5: DONE
    yield SupervisorEvent(
        type=EventType.DONE,
        role=None,
        content=f"Decision was {hitl3_resp.decision.value}, Options: {hitl2_resp.selected_options}"
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def ws_client(monkeypatch):
    """Provides a TestClient connected to a fresh app with mocked SupervisorAgent."""
    # Mock the LLM registry so we don't need real keys
    from src.presentation.api.ws import debate
    monkeypatch.setattr(debate, "get_llm_provider", lambda _: None)
    
    # Mock the ChromaDB store init to avoid creating directories
    from src.infrastructure.rag.chroma_document_store import ChromaDBDocumentStore
    monkeypatch.setattr(ChromaDBDocumentStore, "__init__", lambda self, persist_directory: None)

    # Mock the debate runner
    from src.presentation.api.ws import debate
    monkeypatch.setattr(debate.SupervisorAgent, "run", _fake_debate_generator)

    from src.presentation.api.app import create_app
    app = create_app()
    return TestClient(app)


class TestDebateWebSocket:
    
    def test_missing_start_message_closes_connection(self, ws_client):
        with ws_client.websocket_connect("/ws/debate") as websocket:
            websocket.send_json({"type": "not_start"})
            response = websocket.receive_json()
            assert response["type"] == "error"
            assert "Expected 'start'" in response["content"]
            # Connection is closed after this, next receive would raise an exception

    def test_missing_user_request_closes_connection(self, ws_client):
        with ws_client.websocket_connect("/ws/debate") as websocket:
            websocket.send_json({"type": "start", "user_request": ""})
            response = websocket.receive_json()
            assert response["type"] == "error"
            assert "user_request is required" in response["content"]

    def test_successful_debate_flow_with_hitl_approval(self, ws_client):
        with ws_client.websocket_connect("/ws/debate") as websocket:
            # 1. Init
            websocket.send_json({
                "type": "start",
                "user_request": "Build a caching layer",
                "provider": "gemini"
            })
            
            # 2. First event from generator
            ev1 = websocket.receive_json()
            if ev1["type"] == "error":
                pytest.fail(f"WebSocket error received: {ev1.get('content')}")
            assert ev1["type"] == EventType.AGENT_STARTED.value
            assert ev1["role"] == AgentRole.NL_INTERPRETER.value
            
            # 3. HITL 1
            ev2 = websocket.receive_json()
            assert ev2["type"] == EventType.HITL_REQUIRED.value
            assert ev2["metadata"]["checkpoint"] == "1_interpreter"
            websocket.send_json({"type": "hitl_response", "decision": "approve"})
            
            # 4. HITL 2
            ev3 = websocket.receive_json()
            assert ev3["type"] == EventType.HITL_REQUIRED.value
            assert ev3["metadata"]["checkpoint"] == "2_architects"
            websocket.send_json({
                "type": "hitl_response", 
                "decision": "approve",
                "selected_options": ["Option-1"]
            })

            # 5. HITL 3
            ev4 = websocket.receive_json()
            assert ev4["type"] == EventType.HITL_REQUIRED.value
            assert ev4["metadata"]["checkpoint"] == "3_judge"
            websocket.send_json({"type": "hitl_response", "decision": "approve"})
            
            # 6. DONE
            ev5 = websocket.receive_json()
            assert ev5["type"] == EventType.DONE.value
            assert "approve" in ev5["content"]
            assert "Option-1" in ev5["content"]

    def test_malformed_hitl_response_defaults_to_approve(self, ws_client):
        """dict_to_hitl_response falls back to APPROVE to prevent deadlocks."""
        with ws_client.websocket_connect("/ws/debate") as websocket:
            websocket.send_json({"type": "start", "user_request": "Test"})
            
            # Skip to HITL 1
            websocket.receive_json() # AGENT_STARTED
            websocket.receive_json() # HITL 1
            websocket.send_json({"type": "hitl_response", "decision": "i_dont_know"}) # Invalid decision
            
            websocket.receive_json() # HITL 2
            websocket.send_json({"type": "hitl_response", "decision": "i_dont_know"})
            
            websocket.receive_json() # HITL 3
            websocket.send_json({"type": "hitl_response", "decision": "i_dont_know"})
            
            # Verify fallback worked
            ev = websocket.receive_json()
            assert ev["type"] == EventType.DONE.value
            assert "approve" in ev["content"]

    def test_debate_records_observability_traces(self, ws_client, monkeypatch):
        """Verifies start_trace, spans, and end_trace are emitted to observability service."""
        from unittest.mock import MagicMock
        from src.domain.ports.observability_port import TraceContext, SpanContext
        from src.presentation.api.ws import debate

        mock_obs = MagicMock()
        mock_obs.start_trace.return_value = TraceContext(trace_id="t1", session_id="s1", name="test")
        mock_obs.start_agent_span.return_value = SpanContext(span_id="sp1", trace_id="t1", name="span", agent_role="nl_interpreter")
        monkeypatch.setattr(debate, "get_observability_service", lambda: mock_obs)


        with ws_client.websocket_connect("/ws/debate") as websocket:
            websocket.send_json({"type": "start", "user_request": "Build observability"})
            
            # Consume events
            websocket.receive_json() # AGENT_STARTED
            websocket.receive_json() # HITL 1
            websocket.send_json({"type": "hitl_response", "decision": "approve"})
            websocket.receive_json() # HITL 2
            websocket.send_json({"type": "hitl_response", "decision": "approve"})
            websocket.receive_json() # HITL 3
            websocket.send_json({"type": "hitl_response", "decision": "approve"})
            websocket.receive_json() # DONE

        assert mock_obs.start_trace.called
        assert mock_obs.start_agent_span.called
        assert mock_obs.end_trace.called

