"""
Presentation WS Adapter: DebateObservabilityTracker

Encapsulates trace creation, agent span lifecycle, HITL decision scoring,
and error trace termination for WebSocket debate executions.
"""
from __future__ import annotations

import logging
from typing import Any

from src.domain.agents.supervisor_events import HITLDecision, HITLResponse, SupervisorEvent, EventType
from src.domain.ports.agent_catalog_repository import IAgentCatalogRepository
from src.domain.ports.agent_config_repository import IAgentConfigRepository
from src.domain.ports.observability_service import IObservabilityService, SpanContext, TraceContext

logger = logging.getLogger(__name__)

_HITL_SCORE_MAP: dict[HITLDecision, float] = {
    HITLDecision.APPROVE: 1.0,
    HITLDecision.REFINE: 0.5,
    HITLDecision.DIVERT: 0.5,
    HITLDecision.FINISH: 1.0,
    HITLDecision.REJECT: 0.0,
}


class DebateObservabilityTracker:
    """Tracks trace and child spans across one WebSocket debate session."""

    def __init__(
        self,
        *,
        observability: IObservabilityService,
        agent_catalog: IAgentCatalogRepository,
        agent_config_repo: IAgentConfigRepository,
        default_model: str,
    ) -> None:
        self._observability = observability
        self._agent_catalog = agent_catalog
        self._agent_config_repo = agent_config_repo
        self._default_model = default_model
        self.current_trace: TraceContext | None = None
        self.active_spans: dict[str, SpanContext] = {}

    def build_trace_tags(self, target_agent: str, attachments: list[Any] | None = None) -> list[str]:
        tags = [f"agent:{target_agent}"]
        try:
            profile = self._agent_catalog.get_profile(target_agent)
            flow_tag = "flow:supervisor_debate" if profile.is_supervisor else "flow:sub_agent"
            tags.append(flow_tag)
            if profile.supports_hitl:
                tags.append("has:hitl")
            if profile.uses_rag or profile.can_ingest_documents:
                tags.append("has:rag")
        except KeyError:
            logger.debug("Target agent '%s' not found in catalog when building trace tags", target_agent)
            tags.append("flow:sub_agent")

        if attachments:
            tags.append("has:attachments")
        return tags

    def start_trace(
        self,
        *,
        session_id: str,
        user_request: str,
        target_agent: str,
        user_id: str,
        attachments: list[Any] | None = None,
    ) -> TraceContext:
        self.current_trace = self._observability.start_trace(
            name=f"debate_{target_agent}",
            session_id=session_id,
            user_id=user_id,
            input_data=user_request,
            tags=self.build_trace_tags(target_agent, attachments),
            metadata={"target_agent": target_agent},
        )
        return self.current_trace

    def end_trace(self, status: str, output: str) -> None:
        if not self.current_trace:
            return
        try:
            self._observability.end_trace(
                trace_context=self.current_trace,
                status=status,
                output=output,
            )
        except Exception:
            logger.warning("Failed to end observability trace (status=%s)", status, exc_info=True)
        self.current_trace = None

    def score_hitl_decision(self, hitl_resp: HITLResponse) -> None:
        if not self.current_trace:
            return
        decision_val = (
            hitl_resp.decision.value
            if hasattr(hitl_resp.decision, "value")
            else str(hitl_resp.decision)
        )
        score_val = _HITL_SCORE_MAP.get(hitl_resp.decision, 0.5)
        self._observability.score_trace(
            trace_context=self.current_trace,
            name="hitl_decision",
            value=score_val,
            comment=f"Decision: {decision_val}. Feedback: {hitl_resp.feedback or 'None'}",
        )

    def _on_agent_started(self, event: SupervisorEvent, input_prompt: str) -> None:
        if not (self.current_trace and event.role):
            return
        role_val = event.role.value if hasattr(event.role, "value") else str(event.role)
        config = self._agent_config_repo.find_by_role(role_val)
        default_mod = ""
        try:
            profile = self._agent_catalog.get_profile(role_val)
            default_mod = getattr(profile, "default_model", "")
        except KeyError:
            logger.debug("Agent profile '%s' not found when resolving span model", role_val)

        model_name = config.model_name if (config and config.model_name) else (default_mod or self._default_model)
        self.active_spans[role_val] = self._observability.start_agent_span(
            trace_context=self.current_trace,
            agent_role=role_val,
            input_prompt=input_prompt,
            metadata={"phase": "debate", "model": model_name},
            model_name=model_name,
        )

    def _on_agent_completed(self, event: SupervisorEvent) -> None:
        if not (self.current_trace and event.role):
            return
        role_val = event.role.value if hasattr(event.role, "value") else str(event.role)
        span = self.active_spans.pop(role_val, None)
        if not span:
            return
        meta = event.metadata or {}
        latency = float(meta.get("latency_seconds", 0.0))
        token_counts = {
            "input": int(meta.get("prompt_tokens", 0)),
            "output": int(meta.get("completion_tokens", 0)),
            "total": int(meta.get("total_tokens", meta.get("tokens", 0))),
        }
        model_name = meta.get("model") or getattr(span, "model_name", None)
        self._observability.end_agent_span(
            span_context=span,
            output=event.content,
            token_counts=token_counts,
            latency=latency,
            status="SUCCESS",
            model_name=model_name,
        )

    def track_event(self, event: SupervisorEvent, input_prompt: str = "") -> None:
        if not self.current_trace:
            return
        if event.type == EventType.AGENT_STARTED:
            self._on_agent_started(event, input_prompt)
        elif event.type == EventType.AGENT_COMPLETED:
            self._on_agent_completed(event)
        elif event.type == EventType.DONE:
            self.end_trace("SUCCESS", event.content)

