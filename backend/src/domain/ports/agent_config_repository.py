"""
Domain Port: IAgentConfigRepository
"""
from __future__ import annotations

from typing import List, Optional, Protocol, runtime_checkable

from src.domain.value_objects.agent_config import AgentConfig


@runtime_checkable
class IAgentConfigRepository(Protocol):
    """Port for persisting and resolving per-agent configuration overrides."""

    def save(self, config: AgentConfig) -> None:
        """Saves or updates an agent's configuration."""
        ...

    def find_by_role(self, role: str, user_id: Optional[str] = None) -> Optional[AgentConfig]:
        """Finds an agent's configuration by its role name and optional user_id."""
        ...

    def find_all(self, user_id: Optional[str] = None) -> List[AgentConfig]:
        """Returns all agent configurations, optionally scoped/overridden by user_id."""
        ...

    def delete_by_user_id(self, user_id: str) -> int:
        """Deletes all custom agent configurations for a specific user."""
        ...
