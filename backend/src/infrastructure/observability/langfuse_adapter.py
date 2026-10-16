"""
Infrastructure Adapter: LangfuseObservabilityAdapter
Implements IObservabilityService using the Langfuse SDK with safe graceful degradation.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from src.domain.ports.observability_port import (
    IObservabilityService,
    TraceContext,
    SpanContext,
    SystemMetrics,
    NoOpObservabilityService,
)
from src.infrastructure.observability.system_metrics_collector import SystemMetricsCollector

logger = logging.getLogger(__name__)


class LangfuseObservabilityAdapter(IObservabilityService):
    """
    Adapter integrating the Langfuse Python SDK.
    Degrades gracefully to No-Op behavior if Langfuse is unreachable, offline, or unconfigured.
    """

    def __init__(
        self,
        public_key: str | None = None,
        secret_key: str | None = None,
        host: str | None = None,
        client: Any = None,
        enabled: bool = True,
    ) -> None:
        self._metrics_collector = SystemMetricsCollector()
        self._fallback = NoOpObservabilityService()
        self._active_traces: dict[str, Any] = {}
        self._active_spans: dict[str, Any] = {}

        if not enabled:
            self._client = None
            self._is_enabled = False
        elif client is not None:
            self._client = client
            self._is_enabled = True
        elif public_key and secret_key:
            try:
                from langfuse import Langfuse
                self._client = Langfuse(
                    public_key=public_key,
                    secret_key=secret_key,
                    host=host or "http://localhost:3000",
                )
                self._is_enabled = True
            except Exception as exc:
                logger.warning("Could not initialize Langfuse client: %s. Falling back to NoOp.", exc)
                self._client = None
                self._is_enabled = False
        else:
            self._client = None
            self._is_enabled = False

    @property
    def is_enabled(self) -> bool:
        """Returns True if Langfuse telemetry collection is active."""
        return self._is_enabled


    def start_trace(
        self,
        name: str,
        session_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> TraceContext:
        meta = metadata or {}
        if not self._is_enabled or self._client is None:
            return self._fallback.start_trace(name, session_id, meta)

        try:
            lf_trace = self._client.trace(
                name=name,
                session_id=session_id,
                metadata=meta,
            )
            trace_id = getattr(lf_trace, "id", str(uuid.uuid4()))
            self._active_traces[trace_id] = lf_trace
            return TraceContext(
                trace_id=trace_id,
                session_id=session_id,
                name=name,
                metadata=meta,
            )
        except Exception as exc:
            logger.warning("Failed to start Langfuse trace: %s", exc)
            return self._fallback.start_trace(name, session_id, meta)

    def end_trace(
        self,
        trace_context: TraceContext,
        status: str = "SUCCESS",
        output: Any = None,
    ) -> None:
        if not self._is_enabled:
            return

        lf_trace = self._active_traces.pop(trace_context.trace_id, None)
        if lf_trace and hasattr(lf_trace, "update"):
            try:
                lf_trace.update(status=status, output=output)
            except Exception as exc:
                logger.warning("Failed to update Langfuse trace: %s", exc)

        if self._client and hasattr(self._client, "flush"):
            try:
                self._client.flush()
            except Exception as exc:
                logger.warning("Failed to flush Langfuse client: %s", exc)

    def start_agent_span(
        self,
        trace_context: TraceContext,
        agent_role: str,
        input_prompt: str,
        metadata: dict[str, Any] | None = None,
        model_name: str | None = None,
    ) -> SpanContext:
        meta = metadata or {}
        effective_model = model_name or str(meta.get("model", ""))
        if not self._is_enabled:
            return self._fallback.start_agent_span(
                trace_context, agent_role, input_prompt, meta, model_name=effective_model
            )

        lf_trace = self._active_traces.get(trace_context.trace_id)
        if lf_trace:
            try:
                span_name = f"{agent_role}_execution"
                span_meta = {"role": agent_role, **meta}
                if effective_model:
                    span_meta["model"] = effective_model

                lf_span = None
                if hasattr(lf_trace, "generation"):
                    gen_kwargs: dict[str, Any] = {
                        "name": span_name,
                        "input": input_prompt,
                        "metadata": span_meta,
                    }
                    if effective_model:
                        gen_kwargs["model"] = effective_model
                    lf_span = lf_trace.generation(**gen_kwargs)
                elif hasattr(lf_trace, "span"):
                    lf_span = lf_trace.span(
                        name=span_name,
                        input=input_prompt,
                        metadata=span_meta,
                    )

                if lf_span is not None:
                    span_id = getattr(lf_span, "id", str(uuid.uuid4()))
                    self._active_spans[span_id] = lf_span
                    return SpanContext(
                        span_id=span_id,
                        trace_id=trace_context.trace_id,
                        name=span_name,
                        agent_role=agent_role,
                        metadata=meta,
                        model_name=effective_model,
                    )
            except Exception as exc:
                logger.warning("Failed to start Langfuse span: %s", exc)

        return self._fallback.start_agent_span(
            trace_context, agent_role, input_prompt, meta, model_name=effective_model
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
        if not self._is_enabled:
            return

        lf_span = self._active_spans.pop(span_context.span_id, None)
        if lf_span and hasattr(lf_span, "end"):
            try:
                effective_model = (
                    model_name
                    or getattr(span_context, "model_name", "")
                    or str(span_context.metadata.get("model", ""))
                )
                tokens = token_counts or {}
                in_tkn = int(tokens.get("input", tokens.get("prompt", 0)))
                out_tkn = int(tokens.get("output", tokens.get("completion", 0)))
                tot_tkn = int(tokens.get("total", in_tkn + out_tkn))

                end_kwargs: dict[str, Any] = {
                    "output": output,
                    "metadata": {
                        "latency": latency,
                        "tokens": tokens,
                        **({"model": effective_model} if effective_model else {}),
                    },
                }
                if effective_model:
                    end_kwargs["model"] = effective_model

                if tot_tkn > 0:
                    end_kwargs["usage"] = {
                        "unit": "TOKENS",
                        "input": in_tkn,
                        "output": out_tkn,
                        "total": tot_tkn,
                    }

                lf_span.end(**end_kwargs)
            except Exception as exc:
                logger.warning("Failed to end Langfuse span: %s", exc)

        if self._client and hasattr(self._client, "flush"):
            try:
                self._client.flush()
            except Exception as exc:
                logger.warning("Failed to flush Langfuse client: %s", exc)


    def get_system_metrics(self) -> SystemMetrics:
        return self._metrics_collector.collect()
