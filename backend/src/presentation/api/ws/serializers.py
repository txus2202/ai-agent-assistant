"""
Presentation: WS serializers

Converts SupervisorEvent → dict (for JSON over WebSocket)
and raw dict → HITLResponse (from client JSON).
"""
from __future__ import annotations

from src.domain.agents.supervisor_events import (
    HITLDecision,
    HITLResponse,
    SupervisorEvent,
)


def event_to_dict(event: SupervisorEvent) -> dict:
    """Serialize a SupervisorEvent to a JSON-safe dict for WebSocket transmission."""
    if event.role is None or isinstance(event.role, str):
        role_val = event.role
    else:
        role_val = event.role.value
    return {
        "type": event.type.value,
        "role": role_val,
        "content": event.content,
        "metadata": event.metadata or {},
    }


def dict_to_hitl_response(raw: dict) -> HITLResponse:
    """
    Parse a raw client WebSocket message into a HITLResponse.

    Expected format:
        { "type": "hitl_response", "decision": "approve"|"reject"|"refine", "feedback": "..." }

    Falls back to APPROVE on invalid decision (avoids WebSocket deadlock).
    """
    raw_type = str(raw.get("type", "")).lower()
    raw_decision = str(raw.get("decision", "approve")).lower()
    if raw_type in ("cancel", "abort") or raw_decision in ("cancel", "abort"):
        raise ValueError("Cancellation payload is not a HITL decision")

    try:
        decision = HITLDecision(raw_decision)
    except ValueError:
        decision = HITLDecision.APPROVE

    feedback = raw.get("feedback", "") or ""
    selected_options = raw.get("selected_options", [])
    if not isinstance(selected_options, list):
        selected_options = []
        
    target_agents = raw.get("target_agents", [])
    if not isinstance(target_agents, list):
        target_agents = []
        
    return HITLResponse(
        decision=decision,
        feedback=feedback,
        selected_options=selected_options,
        target_agents=target_agents,
    )
