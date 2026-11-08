"""
RED Tests: LangfuseObservabilityAdapter and SystemMetricsCollector (Feature: feature_observability.md)
"""
from unittest.mock import MagicMock, patch
import pytest

from src.domain.ports.observability_port import IObservabilityService, TraceContext, SpanContext
from src.infrastructure.observability.system_metrics_collector import SystemMetricsCollector
from src.infrastructure.observability.langfuse_adapter import LangfuseObservabilityAdapter


def test_system_metrics_collector_returns_valid_metrics():
    mock_psutil = MagicMock()
    mock_psutil.cpu_percent.return_value = 35.5
    mock_psutil.virtual_memory.return_value = MagicMock(percent=62.0)

    with patch.dict("sys.modules", {"psutil": mock_psutil}):
        collector = SystemMetricsCollector()
        metrics = collector.collect()
        
        assert metrics.cpu_percent == 35.5
        assert metrics.memory_percent == 62.0
        assert metrics.cluster_status == "HEALTHY"


def test_system_metrics_collector_fallback_without_psutil():
    with patch.dict("sys.modules", {"psutil": None}):
        collector = SystemMetricsCollector()
        metrics = collector.collect()
        
        assert metrics.cpu_percent >= 0.0
        assert metrics.memory_percent >= 0.0
        assert metrics.cluster_status == "HEALTHY"


def test_langfuse_adapter_graceful_degradation_when_unconfigured():
    # If no keys or client initialization fails, it should degrade gracefully without errors
    adapter = LangfuseObservabilityAdapter(public_key="", secret_key="", host="")
    assert isinstance(adapter, IObservabilityService)

    trace = adapter.start_trace("test_debate", "session-99")
    assert isinstance(trace, TraceContext)

    span = adapter.start_agent_span(trace, "the_judge", "prompt")
    assert isinstance(span, SpanContext)

    adapter.end_agent_span(span, output="analysis", token_counts={"total": 50}, latency=1.2)
    adapter.end_trace(trace, status="SUCCESS")

    metrics = adapter.get_system_metrics()
    assert metrics.cluster_status == "HEALTHY"


def test_langfuse_adapter_with_active_mock_client():
    mock_langfuse_client = MagicMock()
    mock_trace = MagicMock()
    mock_trace.id = "lf-trace-123"
    mock_langfuse_client.trace.return_value = mock_trace

    mock_span = MagicMock()
    mock_span.id = "lf-span-456"
    mock_trace.generation.return_value = mock_span
    mock_trace.span.return_value = mock_span

    adapter = LangfuseObservabilityAdapter(client=mock_langfuse_client)

    trace = adapter.start_trace(
        name="arch_debate",
        session_id="session-1",
        user_id="user-99",
        input_data="Crear login",
        tags=["flow:sub_agent", "agent:fidias"],
        metadata={"env": "test"},
    )
    assert trace.trace_id == "lf-trace-123"
    assert trace.user_id == "user-99"
    assert trace.tags == ["flow:sub_agent", "agent:fidias"]
    mock_langfuse_client.trace.assert_called_once_with(
        name="arch_debate",
        session_id="session-1",
        user_id="user-99",
        input="Crear login",
        tags=["flow:sub_agent", "agent:fidias"],
        metadata={"env": "test"},
    )

    adapter.score_trace(trace, name="hitl_decision", value=1.0, comment="Aprobado por el usuario")
    mock_trace.score.assert_called_once_with(
        name="hitl_decision",
        value=1.0,
        comment="Aprobado por el usuario",
    )

    span = adapter.start_agent_span(trace, "innovator", "propose microservices", model_name="gemini-1.5-flash")
    assert span.span_id == "lf-span-456"
    assert span.model_name == "gemini-1.5-flash"
    mock_trace.generation.assert_called_once()

    adapter.end_agent_span(span, output="proposals", token_counts={"input": 20, "output": 30}, latency=0.85)
    mock_span.end.assert_called_once_with(
        output="proposals",
        metadata={"latency": 0.85, "tokens": {"input": 20, "output": 30}, "model": "gemini-1.5-flash"},
        model="gemini-1.5-flash",
        usage={"unit": "TOKENS", "input": 20, "output": 30, "total": 50},
    )

    adapter.end_trace(trace, status="SUCCESS", output="final consensus")
    mock_trace.update.assert_called_once_with(status="SUCCESS", output="final consensus")


def test_langfuse_adapter_fallback_to_span_if_no_generation():
    mock_langfuse_client = MagicMock()
    mock_trace = MagicMock(spec=["id", "span", "update"])
    mock_trace.id = "lf-trace-legacy"
    mock_langfuse_client.trace.return_value = mock_trace

    mock_span = MagicMock()
    mock_span.id = "lf-span-legacy"
    mock_trace.span.return_value = mock_span

    adapter = LangfuseObservabilityAdapter(client=mock_langfuse_client)
    trace = adapter.start_trace("arch_debate", "session-leg")
    span = adapter.start_agent_span(trace, "innovator", "propose microservices")
    assert span.span_id == "lf-span-legacy"
    mock_trace.span.assert_called_once()


def test_langfuse_adapter_when_disabled():
    mock_client = MagicMock()
    adapter = LangfuseObservabilityAdapter(client=mock_client, enabled=False)

    assert adapter.is_enabled is False

    trace = adapter.start_trace("arch_debate", "session-disabled")
    assert isinstance(trace, TraceContext)
    mock_client.trace.assert_not_called()

    adapter.score_trace(trace, name="hitl_decision", value=0.5)

    span = adapter.start_agent_span(trace, "innovator", "some prompt")
    assert isinstance(span, SpanContext)

    adapter.end_agent_span(span, output="some output")
    adapter.end_trace(trace, status="SUCCESS")

    mock_client.flush.assert_not_called()

