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
    from unittest.mock import AsyncMock, MagicMock
    from src.application.services.auth_service import AuthService
    from src.application.services.llm_provider_registry import LLMProviderRegistry
    from src.domain.entities.user import User
    from src.presentation.api.ws import debate

    # Mock the ChromaDB store init to avoid creating directories
    from src.infrastructure.rag.chroma_document_store import ChromaDBDocumentStore
    monkeypatch.setattr(ChromaDBDocumentStore, "__init__", lambda self, *a, **kw: None)

    # Mock the debate runner
    monkeypatch.setattr(debate.SupervisorAgent, "run", _fake_debate_generator)

    mock_auth = MagicMock(spec=AuthService)
    mock_auth.is_initialized = AsyncMock(return_value=True)
    test_user = User(id="usr-test-ws", username="architect", password_hash="h", is_admin=True, is_active=True)
    mock_auth.validate_token = AsyncMock(return_value=test_user)

    mock_registry = LLMProviderRegistry()
    mock_registry.register("gemini", MagicMock())

    from src.presentation.api.app import create_app
    app = create_app(auth_service=mock_auth, llm_registry=mock_registry)
    return TestClient(app, cookies={"atenea_session": "mock_valid_ws_token"})


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
        from src.domain.ports.observability_service import TraceContext, SpanContext
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
            assert ev_completed["metadata"]["total_tokens"] == "30"

            ev_done = websocket.receive_json()
            assert ev_done["type"] == EventType.DONE.value
            assert ev_done["metadata"].get("metrics_reported") == "true"
            assert "total_tokens" not in ev_done["metadata"]
            assert "tokens" not in ev_done["metadata"]

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
        record = repo.find_by_id(session_id, allow_unscoped=True)
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
    assert captured["document_parser"] is not None
    assert set(captured["extractors"].keys()) == {
        SourceType.PDF,
        SourceType.URL,
        SourceType.MARKDOWN,
        SourceType.IMAGE,
    }


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


def test_debate_learning_multisource_attachments(ws_client, monkeypatch, tmp_path):
    """Metis processes different attachment file extensions with explicit tags."""
    from src.application.services.learn_from_source import LearnFromSource, SourceType, LearnResult
    from src.application.services.ingest_vault import IngestResult
    from src.presentation.api.routes import upload
    from pathlib import Path

    monkeypatch.setattr(upload, "TEMP_UPLOAD_DIR", str(tmp_path / "uploads"))
    user_dir = upload.get_user_upload_dir("usr-test-ws")
    user_dir.mkdir(parents=True, exist_ok=True)

    pdf_file = user_dir / "guide.pdf"
    md_file = user_dir / "architecture.md"
    img_file = user_dir / "diagram.png"
    pdf_file.write_bytes(b"%PDF-1.4")
    md_file.write_text("# Arch", encoding="utf-8")
    img_file.write_bytes(b"\x89PNG")

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
                str(pdf_file),
                str(md_file),
                str(img_file),
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
    assert not pdf_file.exists()
    assert not md_file.exists()
    assert not img_file.exists()


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


def test_debate_observability_enriched_trace_and_hitl_scoring(ws_client, monkeypatch):
    from unittest.mock import MagicMock
    from src.presentation.api.ws import debate
    from src.domain.ports.observability_service import TraceContext

    mock_obs = MagicMock()
    mock_trace = TraceContext(
        trace_id="tr-test-langfuse-999",
        session_id="ses-123",
        name="debate_supervisor",
        user_id="local_user",
        tags=["agent:supervisor", "flow:supervisor_debate", "has:hitl"],
        metadata={"target_agent": "supervisor"},
    )
    mock_obs.start_trace.return_value = mock_trace
    monkeypatch.setattr(debate, "get_observability_service", lambda: mock_obs)

    with ws_client.websocket_connect("/ws/debate") as websocket:
        websocket.send_json({
            "type": "start",
            "user_request": "Diseña una pasarela de pagos con Stripe",
            "provider": "gemini",
            "target_agent": "supervisor",
        })

        ev1 = websocket.receive_json()
        assert ev1["type"] == EventType.AGENT_STARTED.value
        # Trace ID is propagated in event metadata
        assert ev1["metadata"]["trace_id"] == "tr-test-langfuse-999"

        # Check start_trace call arguments
        mock_obs.start_trace.assert_called_once()
        _, kwargs = mock_obs.start_trace.call_args
        assert kwargs["input_data"] == "Diseña una pasarela de pagos con Stripe"
        assert kwargs["user_id"] == "architect"
        assert "flow:supervisor_debate" in kwargs["tags"]
        assert "has:hitl" in kwargs["tags"]

        # HITL 1: approve
        ev2 = websocket.receive_json()
        assert ev2["type"] == EventType.HITL_REQUIRED.value
        websocket.send_json({"type": "hitl_response", "decision": "approve"})

        # HITL 2: approve
        ev3 = websocket.receive_json()
        assert ev3["type"] == EventType.HITL_REQUIRED.value
        websocket.send_json({"type": "hitl_response", "decision": "approve", "selected_options": ["Option-1"]})

        # HITL 3: refine
        ev4 = websocket.receive_json()
        assert ev4["type"] == EventType.HITL_REQUIRED.value
        websocket.send_json({"type": "hitl_response", "decision": "refine", "feedback": "Por favor añade redis"})

        # Final DONE
        ev5 = websocket.receive_json()
        assert ev5["type"] == EventType.DONE.value

        # Check that score_trace was called for the HITL decisions
        mock_obs.score_trace.assert_called()
        score_calls = [c.kwargs for c in mock_obs.score_trace.call_args_list]
        hitl_scores = [c for c in score_calls if c.get("name") == "hitl_decision"]
        assert len(hitl_scores) >= 3
        # First decision was approve (1.0)
        assert hitl_scores[0]["value"] == 1.0
        assert "approve" in hitl_scores[0]["comment"].lower()
        # Third decision was refine (0.5)
        assert hitl_scores[2]["value"] == 0.5
        assert "refine" in hitl_scores[2]["comment"].lower()
        assert "redis" in hitl_scores[2]["comment"].lower()


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


def test_cancel_message_aborts_and_acknowledges(ws_client):
    with ws_client.websocket_connect("/ws/debate") as websocket:
        websocket.send_json({"type": "cancel"})
        resp = websocket.receive_json()
        assert resp["type"] == "done"
        assert resp["role"] == "supervisor"
        assert "cancelado" in resp["content"].lower()


def test_debate_learning_explicit_target_domain_skips_prompting(ws_client, monkeypatch):
    """When target_domain is passed in the start message, Metis ingests immediately without interactive tag/domain question."""
    from src.application.services.learn_from_source import LearnFromSource, LearnResult
    from pathlib import Path

    captured_kwargs = {}

    def fake_learn_run(**kwargs):
        captured_kwargs.update(kwargs)
        return LearnResult(
            source=kwargs.get("source", "text"),
            generated_file=Path("/vault/01_enterprise_architecture/note.md"),
            errors=[],
        )

    monkeypatch.setattr(LearnFromSource, "run", fake_learn_run)

    with ws_client.websocket_connect("/ws/debate") as websocket:
        websocket.send_json({
            "type": "start",
            "session_id": str(uuid.uuid4()),
            "target_agents": ["learning"],
            "user_request": "/learn Directiva de observabilidad corporativa",
            "target_domain": "01_enterprise_architecture",
        })

        ev1 = websocket.receive_json()
        assert ev1["type"] == EventType.AGENT_STARTED.value

        ev2 = websocket.receive_json()
        assert ev2["type"] == EventType.AGENT_COMPLETED.value
        assert captured_kwargs.get("target_domain") == "01_enterprise_architecture"


@pytest.mark.parametrize(
    "malicious_path",
    [
        "../../../app/.env",
        "../../atenea.db",
        "/etc/passwd",
        "/app/data/atenea.db",
        "../other_user/secret.pdf",
        "/tmp/atenea_uploads/other_user/secret.pdf",
        "file:///etc/passwd",
    ],
)
def test_debate_rejects_path_traversal_attachments(ws_client, monkeypatch, tmp_path, malicious_path):
    """WebSocket rejects arbitrary filesystem paths outside the authenticated user's upload directory."""
    from src.application.services.learn_from_source import LearnFromSource
    from src.presentation.api.routes import upload

    monkeypatch.setattr(upload, "TEMP_UPLOAD_DIR", str(tmp_path / "uploads"))
    called = False

    def spy_learn_run(**kwargs):
        nonlocal called
        called = True
        raise AssertionError("LearnFromSource.run must never execute for blocked paths")

    monkeypatch.setattr(LearnFromSource, "run", spy_learn_run)

    with ws_client.websocket_connect("/ws/debate") as websocket:
        websocket.send_json({
            "type": "start",
            "session_id": str(uuid.uuid4()),
            "target_agent": "learning",
            "user_request": "Aprende esto #sec",
            "attachments": [malicious_path],
        })

        err = websocket.receive_json()
        assert err["type"] == "error"
        assert "attachment" in err["content"].lower()

    assert not called


def test_debate_rejects_symlink_escape_attachment(ws_client, monkeypatch, tmp_path):
    """A symlink inside the user upload folder pointing outside must be rejected."""
    from src.application.services.learn_from_source import LearnFromSource
    from src.presentation.api.routes import upload

    monkeypatch.setattr(upload, "TEMP_UPLOAD_DIR", str(tmp_path / "uploads"))
    user_dir = upload.get_user_upload_dir("usr-test-ws")
    user_dir.mkdir(parents=True, exist_ok=True)

    secret_file = tmp_path / "host_secret.txt"
    secret_file.write_text("SECRET_TOKEN=123", encoding="utf-8")
    symlink_path = user_dir / "leak.md"
    symlink_path.symlink_to(secret_file)

    called = False

    def spy_learn_run(**kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(LearnFromSource, "run", spy_learn_run)

    with ws_client.websocket_connect("/ws/debate") as websocket:
        websocket.send_json({
            "type": "start",
            "session_id": str(uuid.uuid4()),
            "target_agent": "learning",
            "user_request": "Aprende esto #sec",
            "attachments": [str(symlink_path)],
        })

        err = websocket.receive_json()
        assert err["type"] == "error"
        assert "attachment" in err["content"].lower()

    assert not called


def test_debate_learning_accepts_opaque_attachment_id_and_deletes_temp_file(ws_client, monkeypatch, tmp_path):
    """Clients can pass the opaque attachment_id returned by /upload and the temp file is purged afterwards."""
    from pathlib import Path
    from src.application.services.learn_from_source import LearnFromSource, LearnResult
    from src.application.services.ingest_vault import IngestResult
    from src.presentation.api.routes import upload

    monkeypatch.setattr(upload, "TEMP_UPLOAD_DIR", str(tmp_path / "uploads"))
    user_dir = upload.get_user_upload_dir("usr-test-ws")
    user_dir.mkdir(parents=True, exist_ok=True)
    uploaded = user_dir / "abc12345_notes.md"
    uploaded.write_text("# Clean Arch", encoding="utf-8")

    seen_sources = []

    def fake_learn_run(**kwargs):
        seen_sources.append(kwargs["source"])
        return LearnResult(
            source=kwargs["source"],
            generated_file=Path("/vault/learned/notes.md"),
            ingest_result=IngestResult(files_processed=1, chunks_upserted=1),
            errors=[],
        )

    monkeypatch.setattr(LearnFromSource, "run", fake_learn_run)

    with ws_client.websocket_connect("/ws/debate") as websocket:
        websocket.send_json({
            "type": "start",
            "session_id": str(uuid.uuid4()),
            "target_agent": "learning",
            "user_request": "Aprende esto #arch",
            "attachments": ["abc12345_notes.md"],
        })

        assert websocket.receive_json()["type"] == EventType.AGENT_STARTED.value
        assert websocket.receive_json()["type"] == EventType.AGENT_COMPLETED.value
        assert websocket.receive_json()["type"] == EventType.DONE.value

    assert seen_sources == [str(uploaded.resolve())]
    assert not uploaded.exists()


def test_dict_to_hitl_response_rejects_cancel_payload():
    from src.presentation.api.ws.serializers import dict_to_hitl_response

    with pytest.raises(ValueError, match="Cancellation"):
        dict_to_hitl_response({"type": "cancel"})

    with pytest.raises(ValueError, match="Cancellation"):
        dict_to_hitl_response({"type": "hitl_response", "decision": "abort"})


def test_cancel_during_hitl_aborts_without_approving_next_phase(ws_client):
    """Sending {type: 'cancel'} while paused at HITL must abort cleanly instead of defaulting to APPROVE."""
    from src.infrastructure.persistence.sqlite_debate_repository import SqliteDebateRepository
    from src.presentation.api.config import get_settings

    session_id = f"cancel-hitl-{uuid.uuid4()}"

    with ws_client.websocket_connect("/ws/debate") as websocket:
        websocket.send_json({
            "type": "start",
            "session_id": session_id,
            "user_request": "Diseñar arquitectura multi-región",
        })

        ev1 = websocket.receive_json()
        assert ev1["type"] == EventType.AGENT_STARTED.value

        ev_hitl1 = websocket.receive_json()
        assert ev_hitl1["type"] == EventType.HITL_REQUIRED.value

        # Cancel mid-HITL instead of responding with hitl_response
        websocket.send_json({"type": "cancel"})

        ev_done = websocket.receive_json()
        assert ev_done["type"] == EventType.DONE.value
        assert "cancelado" in ev_done["content"].lower()
        assert ev_done["metadata"].get("cancelled") == "true"

    repo = SqliteDebateRepository(str(get_settings().sqlite_db_path))
    record = repo.find_by_id(session_id, allow_unscoped=True)
    assert record is not None
    assert record.status == "aborted"


def test_debate_ws_forwards_injected_settings_and_image_generator_to_supervisor(monkeypatch, tmp_path):
    """Composition root WS handler passes default_provider, default_model, review_rounds and IImageGenerator explicitly."""
    from unittest.mock import AsyncMock, MagicMock
    from src.application.services.auth_service import AuthService
    from src.domain.entities.user import User
    from src.domain.ports.image_generator import IImageGenerator
    from src.presentation.api.app import create_app
    from src.presentation.api.config import Settings
    from src.presentation.api.ws import debate

    captured_kwargs: dict = {}

    async def _capturing_supervisor_run(**kwargs):
        captured_kwargs.update(kwargs)
        yield SupervisorEvent(type=EventType.DONE, role="Supervisor", content="ok")

    from src.application.services.llm_provider_registry import LLMProviderRegistry

    monkeypatch.delenv("IMAGE_GENERATION_PROVIDER", raising=False)
    monkeypatch.delenv("IMAGE_PROVIDER", raising=False)
    monkeypatch.setattr(debate.SupervisorAgent, "run", _capturing_supervisor_run)

    mock_registry = LLMProviderRegistry()
    mock_registry.register("openai", MagicMock())

    mock_auth = MagicMock(spec=AuthService)
    mock_auth.is_initialized = AsyncMock(return_value=True)
    mock_auth.validate_token = AsyncMock(
        return_value=User(id="usr-dip", username="tester", password_hash="h", is_admin=True, is_active=True)
    )
    settings = Settings(
        sqlite_db_path=tmp_path / "ws_dip.db",
        auth_secret_key="test_secret_key_32_bytes_minimum_length",
        default_provider="openai",
        default_model="gpt-4o",
        review_rounds=3,
        image_generation_provider="imagen",
    )
    fake_store = MagicMock()
    app = create_app(
        settings=settings,
        auth_service=mock_auth,
        document_store=fake_store,
        llm_registry=mock_registry,
    )
    client = TestClient(app, cookies={"atenea_session": "tok"})

    with client.websocket_connect("/ws/debate") as websocket:
        websocket.send_json({"type": "start", "user_request": "Diseña una arquitectura"})
        ev = websocket.receive_json()
        assert ev["type"] == EventType.DONE.value

    assert captured_kwargs["default_provider"] == "openai"
    assert captured_kwargs["default_model"] == "gpt-4o"
    assert captured_kwargs["review_rounds"] == 3
    assert isinstance(captured_kwargs["image_generator"], IImageGenerator)
    assert captured_kwargs["image_generator"].get_provider_name() == "imagen"










