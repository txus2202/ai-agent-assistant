"""
Domain: Supervisor Events

Typed event model for the SupervisorAgent debate flow.
These types are infrastructure-agnostic — they work with synchronous
callbacks (Phase 3), WebSockets (Phase 4), and ADK (Phase 4+).

Lives in domain/agents/ because the event vocabulary is a core
business concept, not an infrastructure detail (ADR-015).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from src.domain.agents.agent_role import AgentRole


class EventType(Enum):
    AGENT_STARTED  = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    HITL_REQUIRED  = "hitl_required"
    DONE           = "done"


@dataclass(frozen=True)
class SupervisorEvent:
    """
    An immutable event emitted by SupervisorAgent during the debate flow.

    Attributes:
        type:     The type of event (see EventType).
        role:     The AgentRole that produced this event. None for DONE and HITL events.
        content:  Agent output text, HITL summary, or final consolidated response.
        metadata: Arbitrary key-value context (e.g. checkpoint number, iteration).
    """
    type: EventType
    content: str
    role: AgentRole | None = None
    metadata: dict[str, str] = field(default_factory=dict)


class HITLDecision(Enum):
    APPROVE = "approve"
    REJECT  = "reject"
    REFINE  = "refine"   # user provides additional context; no re-run of previous agents


@dataclass
class HITLResponse:
    """
    User's response to a HITL checkpoint.

    Attributes:
        decision: APPROVE / REJECT / REFINE.
        feedback: Required when decision == REFINE. Appended to subsequent agent prompts.
        selected_options: Identifiers of the solutions selected by the user for the next phase.
    """
    decision: HITLDecision
    feedback: str = ""
    selected_options: list[str] = field(default_factory=list)

