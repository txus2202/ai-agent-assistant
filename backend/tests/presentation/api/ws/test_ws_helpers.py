"""
Unit tests for decomposed WS helpers (`learning_command_parser` & `DebateObservabilityTracker`).
"""
from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

from src.domain.agents.sub_agent_profiles import SubAgentProfile
from src.domain.agents.supervisor_events import EventType, HITLDecision, HITLResponse, SupervisorEvent
from src.domain.ports.observability_service import SpanContext, TraceContext
from src.infrastructure.config.yaml_agent_catalog import InMemoryAgentCatalogRepository
from src.presentation.api.ws.debate_observability_tracker import DebateObservabilityTracker
from src.presentation.api.ws.learning_command_parser import (
    detect_source_type,
    extract_domain,
    extract_tags,
    find_pending_learning_in_events,
    is_skip_tags_response,
    parse_pending_learning_payload,
    resolve_pending_tags,
    validate_attachments,
)
from src.domain.ports.source_extractor import SourceType


def test_learning_command_parser_extracts_tags_domain_and_pending():
    msg = "aprende esto con etiquetas: seguridad, oauth2 #zero_trust en arquitectura empresarial"
    assert extract_tags(msg) == ["seguridad", "oauth2", "zero_trust"]
    assert extract_domain(msg) == "01_enterprise_architecture"
    assert detect_source_type("https://example.com/doc") == SourceType.URL
    assert detect_source_type("notes.md") == SourceType.MARKDOWN
    assert is_skip_tags_response("sin tags") is True
    assert resolve_pending_tags("arquitectura, backend") == ["arquitectura", "backend"]
    assert parse_pending_learning_payload("{bad json") is None

    events = [
        {"type": "done", "metadata": {"pending_learning": '{"text": "algo", "attachments": []}'}},
        {"type": "user_message", "content": "#tag"},
    ]
    assert find_pending_learning_in_events(events) == {"text": "algo", "attachments": []}


def test_validate_attachments_preserves_urls_and_resolves_paths():
    resolved = validate_attachments(
        ["https://example.com/a.pdf", "att-1"],
        "usr-1",
        lambda item, uid: Path(f"/safe/{uid}/{item}.pdf"),
    )
    assert resolved == ["https://example.com/a.pdf", "/safe/usr-1/att-1.pdf"]


def test_observability_tracker_logs_end_trace_failures(caplog):
    mock_obs = MagicMock()
    mock_obs.start_trace.return_value = TraceContext(trace_id="t1", session_id="s1", name="debate")
    mock_obs.start_agent_span.return_value = SpanContext(
        span_id="sp1", trace_id="t1", name="span", agent_role="Spec"
    )
    mock_obs.end_trace.side_effect = RuntimeError("langfuse down")

    catalog = InMemoryAgentCatalogRepository([
        SubAgentProfile(
            id="sup",
            display_name="Sup",
            description="Sup",
            color_hex="#000000",
            system_prompt="Prompt",
            is_supervisor=True,
            supports_hitl=True,
        )
    ])
    config_repo = MagicMock()
    config_repo.find_by_role.return_value = None

    tracker = DebateObservabilityTracker(
        observability=mock_obs,
        agent_catalog=catalog,
        agent_config_repo=config_repo,
        default_model="test-model",
    )
    trace = tracker.start_trace(
        session_id="s1",
        user_request="hello",
        target_agent="sup",
        user_id="alice",
        attachments=[],
    )
    assert trace.trace_id == "t1"
    tracker.track_event(SupervisorEvent(type=EventType.AGENT_STARTED, role="unknown", content=""))
    tracker.score_hitl_decision(HITLResponse(decision=HITLDecision.APPROVE))

    with caplog.at_level(logging.WARNING, logger="src.presentation.api.ws.debate_observability_tracker"):
        tracker.end_trace("ERROR", "boom")

    assert tracker.current_trace is None
    assert "Failed to end observability trace" in caplog.text

