"""
Domain Port: IObservabilityService & Telemetry Value Objects
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class TraceContext:
    """Represents the context of an active trace / debate session."""
    trace_id: str
    session_id: str
    name: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SpanContext:
    """Represents a specific operation / sub-agent execution within a trace."""
    span_id: str
    trace_id: str
    name: str
    agent_role: str
    metadata: dict[str, Any] = field(default_factory=dict)
    model_name: str = ""


@dataclass(frozen=True)
class SystemMetrics:
    """Represents instantaneous host and cluster telemetry metrics."""
    cpu_percent: float
    memory_percent: float
    cluster_status: str = "HEALTHY"
    active_agents_count: int = 0
    additional_stats: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class IObservabilityService(Protocol):
    """
    Port for system-wide observability, tracing, and metric reporting.
    Hexagonal abstraction to decouple Domain/Application from concrete telemetry providers (Langfuse, OpenTelemetry).
    """

    def start_trace(
        self,
        name: str,
        session_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> TraceContext:
        """Initialize a new trace for a session / debate."""
        ...

    def end_trace(
        self,
        trace_context: TraceContext,
        status: str = "SUCCESS",
        output: Any = None,
    ) -> None:
        """Conclude an active trace."""
        ...

    def start_agent_span(
        self,
        trace_context: TraceContext,
        agent_role: str,
        input_prompt: str,
        metadata: dict[str, Any] | None = None,
        model_name: str | None = None,
    ) -> SpanContext:
        """Start a child span representing a specialist agent's generation or retrieval step."""
        ...

    def end_agent_span(
        self,
        span_context: SpanContext,
        output: str,
        token_counts: dict[str, int] | None = None,
        latency: float = 0.0,
        status: str = "SUCCESS",
        model_name: str | None = None,
    ) -> None:
        """Conclude an agent's span with metrics and output."""
        ...

    def get_system_metrics(self) -> SystemMetrics:
        """Fetch current hardware and agent status metrics."""
        ...


class NoOpObservabilityService:
    """Safe fallback implementation that performs no-op when telemetry is disabled or unreachable."""

    def start_trace(
        self,
        name: str,
        session_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> TraceContext:
        return TraceContext(
            trace_id=str(uuid.uuid4()),
            session_id=session_id,
            name=name,
            metadata=metadata or {},
        )

    def end_trace(
        self,
        trace_context: TraceContext,
        status: str = "SUCCESS",
        output: Any = None,
    ) -> None:
        # No-op implementation when telemetry is disabled or unconfigured
        pass

    def start_agent_span(
        self,
        trace_context: TraceContext,
        agent_role: str,
        input_prompt: str,
        metadata: dict[str, Any] | None = None,
        model_name: str | None = None,
    ) -> SpanContext:
        meta = dict(metadata or {})
        if input_prompt:
            meta["input_prompt"] = input_prompt
        return SpanContext(
            span_id=str(uuid.uuid4()),
            trace_id=trace_context.trace_id,
            name=f"{agent_role}_execution",
            agent_role=agent_role,
            metadata=meta,
            model_name=model_name or "",
        )

    def end_agent_span(
        self,
        span_context: SpanContext,
        output: str,
        token_counts: dict[str, int] | None = None,
        latency: float = 0.0,
        status: str = "SUCCESS",
        model_name: str | None = None,
    ) -> None:
        # No-op implementation when telemetry is disabled or unconfigured
        pass

    def get_system_metrics(self) -> SystemMetrics:
        return SystemMetrics(
            cpu_percent=0.0,
            memory_percent=0.0,
            cluster_status="HEALTHY",
            active_agents_count=0,
        )
