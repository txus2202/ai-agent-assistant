"""
Presentation: WS serializers

Converts SupervisorEvent → dict (for JSON over WebSocket)
and raw dict → HITLResponse (from client JSON).
"""
from __future__ import annotations

from src.domain.agents.supervisor_events import (
    EventType,
    HITLDecision,
    HITLResponse,
    SupervisorEvent,
)


def event_to_dict(event: SupervisorEvent) -> dict:
    """Serialize a SupervisorEvent to a JSON-safe dict for WebSocket transmission."""
    return {
        "type": event.type.value,
        "role": event.role.value if event.role is not None else None,
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
    raw_decision = str(raw.get("decision", "approve")).lower()
    try:
        decision = HITLDecision(raw_decision)
    except ValueError:
        decision = HITLDecision.APPROVE

    feedback = raw.get("feedback", "") or ""
    selected_options = raw.get("selected_options", [])
    if not isinstance(selected_options, list):
        selected_options = []
        
    return HITLResponse(decision=decision, feedback=feedback, selected_options=selected_options)
