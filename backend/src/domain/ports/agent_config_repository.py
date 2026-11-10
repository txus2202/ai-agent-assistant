from abc import ABC, abstractmethod
from typing import List, Optional
from src.domain.value_objects.agent_config import AgentConfig

class IAgentConfigRepository(ABC):
    @abstractmethod
    def save(self, config: AgentConfig) -> None:
        """Saves or updates an agent's configuration."""

    @abstractmethod
    def find_by_role(self, role: str, user_id: Optional[str] = None) -> Optional[AgentConfig]:
        """Finds an agent's configuration by its role name and optional user_id."""

    @abstractmethod
    def find_all(self, user_id: Optional[str] = None) -> List[AgentConfig]:
        """Returns all agent configurations, optionally scoped/overridden by user_id."""

    @abstractmethod
    def delete_by_user_id(self, user_id: str) -> int:
        """Deletes all custom agent configurations for a specific user."""

