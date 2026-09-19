from abc import ABC, abstractmethod
from typing import List, Optional
from src.domain.value_objects.agent_config import AgentConfig

class IAgentConfigRepository(ABC):
    @abstractmethod
    def save(self, config: AgentConfig) -> None:
        """Saves or updates an agent's configuration."""

    @abstractmethod
    def find_by_role(self, role: str) -> Optional[AgentConfig]:
        """Finds an agent's configuration by its role name."""

    @abstractmethod
    def find_all(self) -> List[AgentConfig]:
        """Returns all agent configurations."""
