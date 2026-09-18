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

from src.domain.agents.agent_role import AgentRole
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
      2. HITL_REQUIRED
      3. DONE
    """
    hitl_callback = kwargs.get("hitl_callback")
    
    # Event 1
    yield SupervisorEvent(
        type=EventType.AGENT_STARTED,
        role=AgentRole.NL_INTERPRETER,
        content="starting"
    )
    
    # Event 2: HITL
    hitl_event = SupervisorEvent(
        type=EventType.HITL_REQUIRED,
        role=None,
        content="Please review",
        metadata={"checkpoint": "1"}
    )
    yield hitl_event
    
    # The real Supervisor blocks awaiting hitl_callback.
    # Our mock simulates this by calling it.
    hitl_resp = await hitl_callback(hitl_event)
    
    # Event 3: DONE (we inject the decision into the content to verify it passed through)
    yield SupervisorEvent(
        type=EventType.DONE,
        role=None,
        content=f"Decision was {hitl_resp.decision.value}"
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def ws_client(monkeypatch):
    """Provides a TestClient connected to a fresh app with mocked SupervisorAgent."""
    # Mock the LLM registry so we don't need real keys
    from src.infrastructure.llm import registry
    monkeypatch.setattr(registry, "get_llm_provider", lambda _: None)
    
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
            assert ev1["type"] == EventType.AGENT_STARTED.value
            assert ev1["role"] == AgentRole.NL_INTERPRETER.value
            
            # 3. Second event: HITL
            ev2 = websocket.receive_json()
            assert ev2["type"] == EventType.HITL_REQUIRED.value
            assert ev2["metadata"]["checkpoint"] == "1"
            
            # 4. Client responds to HITL
            websocket.send_json({
                "type": "hitl_response",
                "decision": "approve",
                "feedback": ""
            })
            
            # 5. Third event: DONE
            ev3 = websocket.receive_json()
            assert ev3["type"] == EventType.DONE.value
            assert "approve" in ev3["content"]

    def test_malformed_hitl_response_defaults_to_approve(self, ws_client):
        """dict_to_hitl_response falls back to APPROVE to prevent deadlocks."""
        with ws_client.websocket_connect("/ws/debate") as websocket:
            websocket.send_json({"type": "start", "user_request": "Test"})
            
            # Skip to HITL
            websocket.receive_json() # AGENT_STARTED
            websocket.receive_json() # HITL_REQUIRED
            
            # Send invalid decision
            websocket.send_json({
                "type": "hitl_response",
                "decision": "i_dont_know_what_im_doing"
            })
            
            # Verify fallback worked
            ev3 = websocket.receive_json()
            assert ev3["type"] == EventType.DONE.value
            assert "approve" in ev3["content"]
