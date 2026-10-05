"""
Domain: AgentRole

Enum defining all specialized roles in the ATENEA multi-agent system.
Each role corresponds to a SubAgentProfile with a dedicated system prompt
and RAG filter configuration.
"""
from __future__ import annotations

from enum import Enum


class AgentRole(Enum):
    NL_INTERPRETER   = "nl_interpreter"
    INNOVATOR        = "innovator_architect"
    SENIOR_ARCHITECT = "senior_architect"
    THE_JUDGE        = "the_judge"
    DEVOPS_SECOPS    = "devops_secops"
    DIAGRAMMER       = "diagrammer"
    LEARNING         = "learning"
    SUPERVISOR       = "supervisor"
