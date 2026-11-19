"""
Infrastructure Adapter: LangfuseObservabilityAdapter
Implements IObservabilityService using the Langfuse SDK with safe graceful degradation.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from src.domain.ports.observability_service import (
    IObservabilityService,
    TraceContext,
    SpanContext,
    SystemMetrics,
)
from src.infrastructure.observability.noop_observability import NoOpObservabilityService
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
        self._trace_models: dict[str, set[str]] = {}

        if enabled and client is not None:
            self._client = client
            self._is_enabled = True
        elif enabled and public_key and secret_key:
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
        user_id: str | None = None,
        input_data: Any = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TraceContext:
        meta = metadata or {}
        if not self._is_enabled or self._client is None:
            return self._fallback.start_trace(
                name=name,
                session_id=session_id,
                user_id=user_id,
                input_data=input_data,
                tags=tags,
                metadata=meta,
            )

        try:
            trace_kwargs: dict[str, Any] = {
                "name": name,
                "session_id": session_id,
                "metadata": meta,
            }
            if user_id:
                trace_kwargs["user_id"] = user_id
            if input_data is not None:
                trace_kwargs["input"] = input_data
            if tags:
                trace_kwargs["tags"] = tags

            lf_trace = self._client.trace(**trace_kwargs)
            trace_id = getattr(lf_trace, "id", str(uuid.uuid4()))
            self._active_traces[trace_id] = lf_trace
            return TraceContext(
                trace_id=trace_id,
                session_id=session_id,
                name=name,
                user_id=user_id,
                tags=list(tags or []),
                metadata=meta,
            )
        except Exception as exc:
            logger.warning("Failed to start Langfuse trace: %s", exc)
            return self._fallback.start_trace(
                name=name,
                session_id=session_id,
                user_id=user_id,
                input_data=input_data,
                tags=tags,
                metadata=meta,
            )

    def score_trace(
        self,
        trace_context: TraceContext,
        name: str,
        value: float,
        comment: str | None = None,
    ) -> None:
        if not self._is_enabled or self._client is None:
            return

        try:
            lf_trace = self._active_traces.get(trace_context.trace_id)
            score_kwargs: dict[str, Any] = {"name": name, "value": value}
            if comment:
                score_kwargs["comment"] = comment

            if lf_trace and hasattr(lf_trace, "score"):
                lf_trace.score(**score_kwargs)
            elif hasattr(self._client, "score"):
                self._client.score(trace_id=trace_context.trace_id, **score_kwargs)
        except Exception as exc:
            logger.warning("Failed to score Langfuse trace: %s", exc)

        self._flush_client()

    @staticmethod
    def _build_trace_update_kwargs(
        trace_context: TraceContext,
        status: str,
        output: Any,
        models_used: list[str],
    ) -> dict[str, Any]:
        update_kwargs: dict[str, Any] = {"status": status, "output": output}
        if not models_used:
            return update_kwargs

        current_tags = list(trace_context.tags or [])
        for m in models_used:
            tag = f"model:{m}"
            if tag not in current_tags:
                current_tags.append(tag)
        update_kwargs["tags"] = current_tags

        current_meta = dict(trace_context.metadata or {})
        current_meta["models"] = models_used
        update_kwargs["metadata"] = current_meta
        return update_kwargs

    def end_trace(
        self,
        trace_context: TraceContext,
        status: str = "SUCCESS",
        output: Any = None,
    ) -> None:
        if not self._is_enabled:
            return

        lf_trace = self._active_traces.pop(trace_context.trace_id, None)
        models_used = sorted(self._trace_models.pop(trace_context.trace_id, set()))

        if lf_trace and hasattr(lf_trace, "update"):
            try:
                update_kwargs = self._build_trace_update_kwargs(
                    trace_context=trace_context,
                    status=status,
                    output=output,
                    models_used=models_used,
                )
                lf_trace.update(**update_kwargs)
            except Exception as exc:
                logger.warning("Failed to update Langfuse trace: %s", exc)

        self._flush_client()

    def _flush_client(self) -> None:
        if self._client and hasattr(self._client, "flush"):
            try:
                self._client.flush()
            except Exception as exc:
                logger.warning("Failed to flush Langfuse client: %s", exc)

    @staticmethod
    def _create_langfuse_span(
        lf_trace: Any,
        span_name: str,
        input_prompt: str,
        span_meta: dict[str, Any],
        effective_model: str,
    ) -> Any:
        if hasattr(lf_trace, "generation"):
            gen_kwargs: dict[str, Any] = {
                "name": span_name,
                "input": input_prompt,
                "metadata": span_meta,
            }
            if effective_model:
                gen_kwargs["model"] = effective_model
            return lf_trace.generation(**gen_kwargs)
        if hasattr(lf_trace, "span"):
            return lf_trace.span(name=span_name, input=input_prompt, metadata=span_meta)
        return None

    @staticmethod
    def _build_span_usage(tokens: dict[str, int]) -> dict[str, Any] | None:
        in_tkn = int(tokens.get("input", tokens.get("prompt", 0)))
        out_tkn = int(tokens.get("output", tokens.get("completion", 0)))
        tot_tkn = int(tokens.get("total", in_tkn + out_tkn))
        if tot_tkn > 0:
            return {
                "unit": "TOKENS",
                "input": in_tkn,
                "output": out_tkn,
                "total": tot_tkn,
            }
        return None

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
        if effective_model:
            self._trace_models.setdefault(trace_context.trace_id, set()).add(effective_model)
        if lf_trace:
            try:
                span_name = f"{agent_role}_execution"
                span_meta = {"role": agent_role, **meta}
                if effective_model:
                    span_meta["model"] = effective_model

                lf_span = self._create_langfuse_span(
                    lf_trace, span_name, input_prompt, span_meta, effective_model
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
        effective_model = (
            model_name
            or getattr(span_context, "model_name", "")
            or str(span_context.metadata.get("model", ""))
        )
        if effective_model:
            self._trace_models.setdefault(span_context.trace_id, set()).add(effective_model)

        if lf_span and hasattr(lf_span, "end"):
            try:
                tokens = token_counts or {}
                meta_dict: dict[str, Any] = {"latency": latency, "tokens": tokens}
                if effective_model:
                    meta_dict["model"] = effective_model

                end_kwargs: dict[str, Any] = {
                    "output": output,
                    "metadata": meta_dict,
                }
                if effective_model:
                    end_kwargs["model"] = effective_model

                usage = self._build_span_usage(tokens)
                if usage:
                    end_kwargs["usage"] = usage

                lf_span.end(**end_kwargs)
            except Exception as exc:
                logger.warning("Failed to end Langfuse span: %s", exc)

        self._flush_client()


    def get_system_metrics(self) -> SystemMetrics:
        return self._metrics_collector.collect()
