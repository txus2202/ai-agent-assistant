"""
Domain Entity: Agent

Represents a specialist AI agent in the system. This entity is a pure
Python class with no external framework dependencies, as required by
Clean Architecture rules for the Domain layer.
"""
from __future__ import annotations

import uuid
from enum import Enum


class AgentStatus(Enum):
    """Lifecycle states of an Agent within the system."""
    IDLE = "idle"
    THINKING = "thinking"
    ERROR = "error"


class Agent:
    """
    Core domain entity that represents a specialist AI agent.

    Invariant validations enforced at construction time:
    - ``name``       : must be at least 3 characters (no whitespace-only strings).
    - ``role``       : cannot be empty or consist solely of whitespace.
    - ``provider``   : cannot be empty (free-form string, no enum lock-in).
    - ``model_name`` : cannot be empty (free-form string, no enum lock-in).
    - ``status``     : defaults to ``AgentStatus.IDLE``; must be a valid ``AgentStatus``.
    """

    def __init__(
        self,
        name: str,
        role: str,
        provider: str,
        model_name: str,
        status: AgentStatus = AgentStatus.IDLE,
        agent_id: uuid.UUID | None = None,
    ) -> None:
        self._validate_name(name)
        self._validate_role(role)
        self._validate_provider(provider)
        self._validate_model_name(model_name)
        self._validate_status(status)

        self.id: uuid.UUID = agent_id if agent_id is not None else uuid.uuid4()
        self.name: str = name
        self.role: str = role
        self.provider: str = provider
        self.model_name: str = model_name
        self.status: AgentStatus = status

    # ------------------------------------------------------------------
    # Private validators
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_name(name: str) -> None:
        if not isinstance(name, str) or len(name.strip()) < 3:
            raise ValueError(
                "Agent name must be at least 3 characters long."
            )

    @staticmethod
    def _validate_role(role: str) -> None:
        if not isinstance(role, str) or not role.strip():
            raise ValueError("Agent role cannot be empty or whitespace.")

    @staticmethod
    def _validate_provider(provider: str) -> None:
        if not isinstance(provider, str) or not provider.strip():
            raise ValueError("Provider cannot be empty.")

    @staticmethod
    def _validate_model_name(model_name: str) -> None:
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("Model name cannot be empty.")

    @staticmethod
    def _validate_status(status: AgentStatus) -> None:
        if not isinstance(status, AgentStatus):
            raise ValueError(
                f"Status must be a valid AgentStatus, got: {type(status)}"
            )

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"Agent(id={self.id!r}, name={self.name!r}, "
            f"provider={self.provider!r}, model={self.model_name!r}, "
            f"status={self.status.value!r})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Agent):
            return NotImplemented
        return self.id == other.id
