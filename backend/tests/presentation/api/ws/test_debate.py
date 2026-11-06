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

import uuid
import pytest
from fastapi.testclient import TestClient

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
        role="Hermes",
        content="starting"
    )
    
    # Event 2: HITL 1
    hitl1_event = SupervisorEvent(
        type=EventType.HITL_REQUIRED,
        role="Hermes",
        content="Please review interpretation",
        metadata={"checkpoint": "after_Hermes", "agent": "Hermes"}
    )
    yield hitl1_event
    hitl1_resp = await hitl_callback(hitl1_event)
    
    # Event 3: HITL 2
    hitl2_event = SupervisorEvent(
        type=EventType.HITL_REQUIRED,
        role="Ícaro",
        content="Please review architects",
        metadata={"checkpoint": "after_Ícaro", "agent": "Ícaro"}
    )
    yield hitl2_event
    hitl2_resp = await hitl_callback(hitl2_event)

    # Event 4: HITL 3
    hitl3_event = SupervisorEvent(
        type=EventType.HITL_REQUIRED,
        role="Sphinx",
        content="Please review judge",
        metadata={"checkpoint": "after_Sphinx", "agent": "Sphinx"}
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
    monkeypatch.setattr(ChromaDBDocumentStore, "__init__", lambda self, *a, **kw: None)

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
            assert ev1["role"] in ("Hermes", "nl_interpreter")
            
            # 3. HITL 1
            ev2 = websocket.receive_json()
            assert ev2["type"] == EventType.HITL_REQUIRED.value
            assert ev2["metadata"]["checkpoint"] in ("after_Hermes", "1_interpreter")
            websocket.send_json({"type": "hitl_response", "decision": "approve"})
            
            # 4. HITL 2
            ev3 = websocket.receive_json()
            assert ev3["type"] == EventType.HITL_REQUIRED.value
            assert ev3["metadata"]["checkpoint"] in ("after_Ícaro", "2_architects")
            websocket.send_json({
                "type": "hitl_response", 
                "decision": "approve",
                "selected_options": ["Option-1"]
            })

            # 5. HITL 3
            ev4 = websocket.receive_json()
            assert ev4["type"] == EventType.HITL_REQUIRED.value
            assert ev4["metadata"]["checkpoint"] in ("after_Sphinx", "3_judge")
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

    def test_sub_agent_invocation_with_chat_history(self, ws_client, monkeypatch):
        """Verifies sub_agent invocation propagates chat_history to SubAgentRunner."""
        from unittest.mock import AsyncMock
        from src.application.agents.sub_agent_runner import SubAgentResponse
        from src.presentation.api.ws import debate

        mock_runner = AsyncMock()
        mock_runner.return_value = SubAgentResponse(
            role="Sphinx",
            content="Sphinx review",
            context_chunks=[],
            tokens={"input": 10, "output": 20, "total": 30},
            latency=0.1,
            model_name="test-model"
        )
        monkeypatch.setattr(debate.SubAgentRunner, "run", mock_runner)

        history_payload = [
            {"role": "user", "content": "Hola equipo"},
            {"role": "assistant", "agent": "Atenea", "content": "Bienvenido"},
        ]

        with ws_client.websocket_connect("/ws/debate") as websocket:
            websocket.send_json({
                "type": "start",
                "target_agent": "the_judge",
                "user_request": "Sphinx qué opinas",
                "history": history_payload
            })

            ev_started = websocket.receive_json()
            assert ev_started["type"] == EventType.AGENT_STARTED.value
            assert ev_started["role"] == "Sphinx"

            ev_completed = websocket.receive_json()
            assert ev_completed["type"] == EventType.AGENT_COMPLETED.value
            assert ev_completed["content"] == "Sphinx review"

            ev_done = websocket.receive_json()
            assert ev_done["type"] == EventType.DONE.value

        mock_runner.assert_awaited_once()
        _, kwargs = mock_runner.call_args
        assert kwargs["chat_history"] == history_payload
        assert kwargs["role"] == "Sphinx"
        assert kwargs["user_request"] == "Sphinx qué opinas"

    def test_continuous_chat_session_reuses_session_id_and_appends_events(self, ws_client, monkeypatch):
        """Verifies multiple 'start' messages sharing session_id reuse DebateRecord and append events."""
        from unittest.mock import AsyncMock
        from src.application.agents.sub_agent_runner import SubAgentResponse
        from src.presentation.api.ws import debate
        from src.presentation.api.config import get_settings
        from src.infrastructure.persistence.sqlite_debate_repository import SqliteDebateRepository

        mock_runner = AsyncMock()
        mock_runner.side_effect = [
            SubAgentResponse(
                role="Sphinx",
                content="Sphinx review 1",
                context_chunks=[],
                tokens={"input": 10, "output": 20, "total": 30},
                latency=0.1,
                model_name="test-model"
            ),
            SubAgentResponse(
                role="Hefesto",
                content="Hefesto deploy 2",
                context_chunks=[],
                tokens={"input": 15, "output": 25, "total": 40},
                latency=0.2,
                model_name="test-model"
            )
        ]
        monkeypatch.setattr(debate.SubAgentRunner, "run", mock_runner)

        session_id = f"test-session-{uuid.uuid4()}"

        with ws_client.websocket_connect("/ws/debate") as websocket:
            # Turn 1: Sphinx
            websocket.send_json({
                "type": "start",
                "session_id": session_id,
                "target_agent": "the_judge",
                "user_request": "Sphinx qué opinas",
            })

            ev_started1 = websocket.receive_json()
            assert ev_started1["type"] == EventType.AGENT_STARTED.value
            ev_completed1 = websocket.receive_json()
            assert ev_completed1["type"] == EventType.AGENT_COMPLETED.value
            ev_done1 = websocket.receive_json()
            assert ev_done1["type"] == EventType.DONE.value

            # Turn 2: Hefesto (same session_id)
            websocket.send_json({
                "type": "start",
                "session_id": session_id,
                "target_agent": "devops_secops",
                "user_request": "Hefesto prepara el pipeline",
            })

            ev_started2 = websocket.receive_json()
            assert ev_started2["type"] == EventType.AGENT_STARTED.value
            ev_completed2 = websocket.receive_json()
            assert ev_completed2["type"] == EventType.AGENT_COMPLETED.value
            ev_done2 = websocket.receive_json()
            assert ev_done2["type"] == EventType.DONE.value

        # Verify database record: only 1 DebateRecord for this session_id
        settings = get_settings()
        repo = SqliteDebateRepository(str(settings.sqlite_db_path))
        record = repo.find_by_id(session_id)
        assert record is not None
        assert record.id == session_id
        
        # Verify events contain both user messages and agent responses in chronological order
        event_types = [e.get("type") for e in record.events]
        assert "user_message" in event_types
        user_events = [e for e in record.events if e.get("type") == "user_message"]
        assert len(user_events) == 2
        assert user_events[0]["content"] == "Sphinx qué opinas"
        assert user_events[1]["content"] == "Hefesto prepara el pipeline"


def test_debate_learning_conversational_chat(ws_client, monkeypatch):
    """Metis chats naturally when no attachments and no explicit learning directive are provided."""
    from src.application.agents.sub_agent_runner import SubAgentRunner, SubAgentResponse

    async def fake_subagent_run(*args, **kwargs):
        return SubAgentResponse(
            role="Metis",
            content="Hola, soy Metis. He consultado el vault y aquí tienes la información sobre Clean Architecture.",
            context_chunks=[],
            tokens={"input": 10, "output": 20, "total": 30},
            latency=0.1,
            model_name="mock-model",
        )

    monkeypatch.setattr(SubAgentRunner, "run", fake_subagent_run)

    with ws_client.websocket_connect("/ws/debate") as websocket:
        websocket.send_json({
            "type": "start",
            "session_id": str(uuid.uuid4()),
            "target_agent": "learning",
            "user_request": "¿Qué sabes sobre Clean Architecture?",
        })

        ev_started = websocket.receive_json()
        assert ev_started["type"] == EventType.AGENT_STARTED.value
        assert ev_started["role"] == "Metis"

        ev_completed = websocket.receive_json()
        assert ev_completed["type"] == EventType.AGENT_COMPLETED.value
        assert "Clean Architecture" in ev_completed["content"]

        ev_done = websocket.receive_json()
        assert ev_done["type"] == EventType.DONE.value


def test_debate_learning_explicit_directive_with_tags(ws_client, monkeypatch):
    """Metis detects 'Aprende esto:' directive with tags and completes immediately."""
    from src.application.services.learn_from_source import LearnFromSource, SourceType, LearnResult
    from src.application.services.ingest_vault import IngestResult
    from pathlib import Path

    captured = {}

    def fake_learn_run(**kwargs):
        captured.update(kwargs)
        return LearnResult(
            source=kwargs.get("source", ""),
            generated_file=Path("/vault/concepts/pattern.md"),
            ingest_result=IngestResult(files_processed=1, chunks_upserted=2),
            errors=[],
        )

    monkeypatch.setattr(LearnFromSource, "run", fake_learn_run)

    with ws_client.websocket_connect("/ws/debate") as websocket:
        websocket.send_json({
            "type": "start",
            "session_id": str(uuid.uuid4()),
            "target_agent": "learning",
            "user_request": "Aprende esto #mensajeria: El patrón Outbox garantiza atomicidad en mensajería.",
        })

        ev_started = websocket.receive_json()
        assert ev_started["type"] == EventType.AGENT_STARTED.value

        ev_completed = websocket.receive_json()
        assert ev_completed["type"] == EventType.AGENT_COMPLETED.value
        assert "pattern.md" in ev_completed["content"]
        assert "mensajeria" in ev_completed["content"]

        ev_done = websocket.receive_json()
        assert ev_done["type"] == EventType.DONE.value

    assert captured["source_type"] == SourceType.TEXT
    assert "El patrón Outbox" in captured["source"]
    assert captured["tags"] == ["mensajeria"]


def test_debate_learning_interactive_tag_flow(ws_client, monkeypatch):
    """Metis asks for tags when none are provided, and completes upon user response."""
    from src.application.services.learn_from_source import LearnFromSource, SourceType, LearnResult
    from src.application.services.ingest_vault import IngestResult
    from pathlib import Path

    captured = {}

    def fake_learn_run(**kwargs):
        captured.update(kwargs)
        return LearnResult(
            source=kwargs.get("source", ""),
            generated_file=Path("/vault/concepts/pattern.md"),
            ingest_result=IngestResult(files_processed=1, chunks_upserted=2),
            errors=[],
        )

    monkeypatch.setattr(LearnFromSource, "run", fake_learn_run)
    session_id = str(uuid.uuid4())

    # Turn 1: User sends learning directive without tags
    with ws_client.websocket_connect("/ws/debate") as websocket:
        websocket.send_json({
            "type": "start",
            "session_id": session_id,
            "target_agent": "learning",
            "user_request": "Aprende esto: El patrón CQRS separa comandos y queries.",
        })

        ev_started = websocket.receive_json()
        assert ev_started["type"] == EventType.AGENT_STARTED.value

        ev_completed = websocket.receive_json()
        assert ev_completed["type"] == EventType.AGENT_COMPLETED.value
        assert "¿deseas catalogarlo con algún tag o etiqueta específico" in ev_completed["content"]

        ev_done = websocket.receive_json()
        assert ev_done["type"] == EventType.DONE.value

    # Turn 2: User responds with tags in the same session
    with ws_client.websocket_connect("/ws/debate") as websocket:
        websocket.send_json({
            "type": "start",
            "session_id": session_id,
            "target_agent": "learning",
            "user_request": "#atenea #arquitectura",
        })

        ev_started = websocket.receive_json()
        assert ev_started["type"] == EventType.AGENT_STARTED.value

        ev_completed = websocket.receive_json()
        assert ev_completed["type"] == EventType.AGENT_COMPLETED.value
        assert "pattern.md" in ev_completed["content"]
        assert "atenea" in ev_completed["content"]

        ev_done = websocket.receive_json()
        assert ev_done["type"] == EventType.DONE.value

    assert captured["tags"] == ["atenea", "arquitectura"]


def test_debate_learning_multisource_attachments(ws_client, monkeypatch):
    """Metis processes different attachment file extensions with explicit tags."""
    from src.application.services.learn_from_source import LearnFromSource, SourceType, LearnResult
    from src.application.services.ingest_vault import IngestResult
    from pathlib import Path

    captured_types = []

    def fake_learn_run(**kwargs):
        captured_types.append(kwargs["source_type"])
        return LearnResult(
            source=kwargs.get("source", ""),
            generated_file=Path("/vault/concepts/note.md"),
            ingest_result=IngestResult(files_processed=1, chunks_upserted=2),
            errors=[],
        )

    monkeypatch.setattr(LearnFromSource, "run", fake_learn_run)

    with ws_client.websocket_connect("/ws/debate") as websocket:
        websocket.send_json({
            "type": "start",
            "session_id": str(uuid.uuid4()),
            "target_agent": "learning",
            "user_request": "Metis aprende estos documentos #docs #arquitectura",
            "attachments": [
                "/tmp/guide.pdf",
                "/tmp/architecture.md",
                "/tmp/diagram.png",
                "https://example.com/spec",
            ],
        })

        ev_started = websocket.receive_json()
        assert ev_started["type"] == EventType.AGENT_STARTED.value

        ev_completed = websocket.receive_json()
        assert ev_completed["type"] == EventType.AGENT_COMPLETED.value

        ev_done = websocket.receive_json()
        assert ev_done["type"] == EventType.DONE.value

    assert captured_types == [
        SourceType.PDF,
        SourceType.MARKDOWN,
        SourceType.IMAGE,
        SourceType.URL,
    ]


def test_multi_agent_sequential_dispatch_in_arrival_order(ws_client, monkeypatch):
    """When multiple agents are selected, all of them respond in sequential arrival order."""
    from unittest.mock import AsyncMock
    from src.application.agents.sub_agent_runner import SubAgentRunner, SubAgentResponse

    responses = {
        "Sphinx": SubAgentResponse(
            role="Sphinx",
            content="Análisis de Sphinx",
            tokens={"input": 15, "output": 25, "total": 40},
            latency=0.4,
            model_name="mock-model",
        ),
        "Hefesto": SubAgentResponse(
            role="Hefesto",
            content="Análisis de Hefesto",
            tokens={"input": 20, "output": 30, "total": 50},
            latency=0.6,
            model_name="mock-model",
        ),
    }

    call_order = []

    async def fake_runner_run(role, user_request, **kwargs):
        call_order.append((role, kwargs.get("chat_history", [])))
        return responses[role]

    monkeypatch.setattr(SubAgentRunner, "run", AsyncMock(side_effect=fake_runner_run))

    with ws_client.websocket_connect("/ws/debate") as websocket:
        websocket.send_json({
            "type": "start",
            "session_id": str(uuid.uuid4()),
            "target_agents": ["the_judge", "devops_secops"],
            "user_request": "¿Cuál es vuestra opinión técnica?",
        })

        # Agent 1 (Sphinx): STARTED -> MESSAGE -> COMPLETED
        ev1_started = websocket.receive_json()
        assert ev1_started["type"] == EventType.AGENT_STARTED.value
        assert ev1_started["role"] == "Sphinx"

        ev1_msg = websocket.receive_json()
        assert ev1_msg["type"] == EventType.MESSAGE.value
        assert ev1_msg["role"] == "Sphinx"
        assert ev1_msg["content"] == "Análisis de Sphinx"

        ev1_comp = websocket.receive_json()
        assert ev1_comp["type"] == EventType.AGENT_COMPLETED.value
        assert ev1_comp["role"] == "Sphinx"

        # Agent 2 (Hefesto): STARTED -> MESSAGE -> COMPLETED
        ev2_started = websocket.receive_json()
        assert ev2_started["type"] == EventType.AGENT_STARTED.value
        assert ev2_started["role"] == "Hefesto"

        ev2_msg = websocket.receive_json()
        assert ev2_msg["type"] == EventType.MESSAGE.value
        assert ev2_msg["role"] == "Hefesto"
        assert ev2_msg["content"] == "Análisis de Hefesto"

        ev2_comp = websocket.receive_json()
        assert ev2_comp["type"] == EventType.AGENT_COMPLETED.value
        assert ev2_comp["role"] == "Hefesto"

        # Final DONE event closing the multi-agent turn
        ev_done = websocket.receive_json()
        assert ev_done["type"] == EventType.DONE.value

    # Verify execution order and cumulative history
    assert [call[0] for call in call_order] == ["Sphinx", "Hefesto"]
    # Hefesto received Sphinx's response in its chat_history
    assert any(h.get("agent") == "Sphinx" and h.get("content") == "Análisis de Sphinx" for h in call_order[1][1])


def test_supervisor_exception_emits_single_error_event(ws_client, monkeypatch):
    from src.presentation.api.ws import debate

    async def _failing_generator(*args, **kwargs):
        raise RuntimeError("LLM rate limit exceeded on agent Ícaro")
        if False:
            yield

    monkeypatch.setattr(debate.SupervisorAgent, "run", _failing_generator)

    with ws_client.websocket_connect("/ws/debate") as websocket:
        websocket.send_json({
            "type": "start",
            "user_request": "Diseña una arquitectura",
            "provider": "gemini"
        })
        err_event = websocket.receive_json()
        assert err_event["type"] == "error"
        assert err_event["role"] == "supervisor"
        assert "LLM rate limit exceeded on agent Ícaro" in err_event["content"]





