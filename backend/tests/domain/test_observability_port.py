"""
Domain Tests: IObservabilityService Port and Telemetry Value Objects
"""
from dataclasses import is_dataclass

from src.domain.ports.observability_service import (
    IObservabilityService,
    SpanContext,
    SystemMetrics,
    TraceContext,
)


class _DummyObservabilityService:
    def start_trace(self, name, session_id, user_id=None, input_data=None, tags=None, metadata=None):
        return TraceContext(trace_id="tr-1", session_id=session_id, name=name)

    def end_trace(self, trace_context, status="SUCCESS", output=None):
        pass

    def score_trace(self, trace_context, name, value, comment=None):
        pass

    def start_agent_span(self, trace_context, agent_role, input_prompt, metadata=None, model_name=None):
        return SpanContext(span_id="sp-1", trace_id=trace_context.trace_id, name="span", agent_role=agent_role)

    def end_agent_span(self, span_context, output, token_counts=None, latency=0.0, status="SUCCESS", model_name=None):
        pass

    def get_system_metrics(self):
        return SystemMetrics(cpu_percent=0.0, memory_percent=0.0)


def test_trace_context_attributes():
    ctx = TraceContext(
        trace_id="tr-123",
        session_id="ses-456",
        name="architecture_debate",
        user_id="user-789",
        tags=["flow:debate", "agent:fidias"],
        metadata={"user": "developer"},
    )
    assert is_dataclass(ctx)
    assert ctx.trace_id == "tr-123"
    assert ctx.session_id == "ses-456"
    assert ctx.name == "architecture_debate"
    assert ctx.user_id == "user-789"
    assert ctx.tags == ["flow:debate", "agent:fidias"]
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


def test_observability_protocol_structural_conformance():
    service = _DummyObservabilityService()
    assert isinstance(service, IObservabilityService)

    class _IncompleteService:
        def start_trace(self, name, session_id, user_id=None, input_data=None, tags=None, metadata=None):
            return TraceContext(trace_id="tr-1", session_id=session_id, name=name)

    assert not isinstance(_IncompleteService(), IObservabilityService)
