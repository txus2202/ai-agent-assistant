"""
RED Tests: LangfuseObservabilityAdapter and SystemMetricsCollector (Feature: feature_observability.md)
"""
from unittest.mock import MagicMock, patch
import pytest

from src.domain.ports.observability_service import (
    IObservabilityService,
    SpanContext,
    SystemMetrics,
    TraceContext,
)
from src.infrastructure.observability import NoOpObservabilityService
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
    mock_trace.update.assert_called_once_with(
        status="SUCCESS",
        output="final consensus",
        tags=["flow:sub_agent", "agent:fidias", "model:gemini-1.5-flash"],
        metadata={"env": "test", "models": ["gemini-1.5-flash"]},
    )


def test_langfuse_adapter_tags_multiple_models_in_trace():
    mock_langfuse_client = MagicMock()
    mock_trace = MagicMock()
    mock_trace.id = "lf-trace-multi"
    mock_langfuse_client.trace.return_value = mock_trace

    adapter = LangfuseObservabilityAdapter(client=mock_langfuse_client)
    trace = adapter.start_trace(
        name="multi_agent_debate",
        session_id="session-multi",
        tags=["flow:supervisor_debate", "agent:supervisor"],
    )

    span1 = adapter.start_agent_span(trace, "hermes", "prompt 1", model_name="gemini-3.8-flash")
    adapter.end_agent_span(span1, output="out 1")

    span2 = adapter.start_agent_span(trace, "icaro", "prompt 2", model_name="gemini-3.7-flash")
    adapter.end_agent_span(span2, output="out 2")

    span3 = adapter.start_agent_span(trace, "supervisor", "prompt 3", model_name="gemini-3.1-pro-preview")
    adapter.end_agent_span(span3, output="out 3")

    adapter.end_trace(trace, status="SUCCESS", output="consensus")
    mock_trace.update.assert_called_once_with(
        status="SUCCESS",
        output="consensus",
        tags=[
            "flow:supervisor_debate",
            "agent:supervisor",
            "model:gemini-3.1-pro-preview",
            "model:gemini-3.7-flash",
            "model:gemini-3.8-flash",
        ],
        metadata={
            "models": ["gemini-3.1-pro-preview", "gemini-3.7-flash", "gemini-3.8-flash"]
        },
    )


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


def test_noop_observability_service_satisfies_protocol():
    service = NoOpObservabilityService()
    assert isinstance(service, IObservabilityService)

    trace = service.start_trace(
        name="debate",
        session_id="ses-1",
        user_id="user-42",
        input_data="Necesito una landing page",
        tags=["flow:debate", "agent:fidias"],
    )
    assert isinstance(trace, TraceContext)
    assert trace.user_id == "user-42"
    assert trace.tags == ["flow:debate", "agent:fidias"]

    service.score_trace(trace, name="hitl_decision", value=1.0, comment="Aprobado por el usuario")
    service.end_trace(trace, status="SUCCESS", output="Landing page generada")

    span = service.start_agent_span(trace, agent_role="interpreter", input_prompt="hello")
    assert isinstance(span, SpanContext)
    service.end_agent_span(span, output="structured requirement", token_counts={"total": 120}, latency=0.45)

    sys_metrics = service.get_system_metrics()
    assert isinstance(sys_metrics, SystemMetrics)

