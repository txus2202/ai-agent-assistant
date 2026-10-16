"""
RED Tests: IObservabilityService Port and Value Objects (Feature: feature_observability.md)
"""
from dataclasses import is_dataclass
import pytest
from src.domain.ports.observability_port import (
    IObservabilityService,
    TraceContext,
    SpanContext,
    SystemMetrics,
    NoOpObservabilityService,
)


def test_trace_context_attributes():
    ctx = TraceContext(
        trace_id="tr-123",
        session_id="ses-456",
        name="architecture_debate",
        metadata={"user": "developer"},
    )
    assert is_dataclass(ctx)
    assert ctx.trace_id == "tr-123"
    assert ctx.session_id == "ses-456"
    assert ctx.name == "architecture_debate"
    assert ctx.metadata == {"user": "developer"}


def test_span_context_attributes():
    span = SpanContext(
        span_id="sp-789",
        trace_id="tr-123",
        name="the_judge_critique",
        agent_role="the_judge",
        metadata={"model": "gpt-4o"},
    )
    assert is_dataclass(span)
    assert span.span_id == "sp-789"
    assert span.trace_id == "tr-123"
    assert span.agent_role == "the_judge"


def test_system_metrics_attributes():
    metrics = SystemMetrics(
        cpu_percent=42.5,
        memory_percent=58.0,
        cluster_status="HEALTHY",
        active_agents_count=1,
    )
    assert is_dataclass(metrics)
    assert metrics.cpu_percent == 42.5
    assert metrics.memory_percent == 58.0
    assert metrics.cluster_status == "HEALTHY"
    assert metrics.active_agents_count == 1


def test_noop_observability_service_satisfies_protocol():
    service = NoOpObservabilityService()
    assert isinstance(service, IObservabilityService)

    trace = service.start_trace(name="debate", session_id="ses-1")
    assert isinstance(trace, TraceContext)
    service.end_trace(trace, status="SUCCESS")

    span = service.start_agent_span(trace, agent_role="interpreter", input_prompt="hello")
    assert isinstance(span, SpanContext)
    service.end_agent_span(span, output="structured requirement", token_counts={"total": 120}, latency=0.45)

    sys_metrics = service.get_system_metrics()
    assert isinstance(sys_metrics, SystemMetrics)
