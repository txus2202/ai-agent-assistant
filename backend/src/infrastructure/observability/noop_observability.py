"""
Infrastructure Adapter: NoOpObservabilityService
Safe fallback implementation of IObservabilityService when telemetry is disabled or unreachable.
"""
from __future__ import annotations

import uuid
from typing import Any

from src.domain.ports.observability_service import (
    IObservabilityService,
    SpanContext,
    SystemMetrics,
    TraceContext,
)


class NoOpObservabilityService(IObservabilityService):
    """Safe fallback implementation that performs no-op when telemetry is disabled or unreachable."""

    def start_trace(
        self,
        name: str,
        session_id: str,
        user_id: str | None = None,
        input_data: Any = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceContext:
        meta = dict(metadata or {})
        if input_data is not None:
            meta["input"] = input_data
        return TraceContext(
            trace_id=str(uuid.uuid4()),
            session_id=session_id,
            name=name,
            user_id=user_id,
            tags=list(tags or []),
            metadata=meta,
        )

    def end_trace(
        self,
        trace_context: TraceContext,
        status: str = "SUCCESS",
        output: Any = None,
    ) -> None:
        # No-op implementation when telemetry is disabled or unconfigured
        pass

    def score_trace(
        self,
        trace_context: TraceContext,
        name: str,
        value: float,
        comment: str | None = None,
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

