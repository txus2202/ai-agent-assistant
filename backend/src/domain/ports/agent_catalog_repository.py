"""
Domain Ports: Agent Catalog & Debate Topology

Defines pure abstractions for retrieving agent profile catalogs and multi-agent
debate topologies without coupling domain/application layers to YAML or filesystem I/O.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.agents.debate_topology import DebateTopology
from src.domain.agents.sub_agent_profiles import SubAgentProfile


class IAgentCatalogRepository(ABC):
    """Port for querying and managing registered SubAgentProfile definitions."""

    @abstractmethod
    def get_all_profiles(self) -> list[SubAgentProfile]:
        """Return all registered SubAgentProfile instances in registration order."""

    @abstractmethod
    def get_profile(self, identifier: str) -> SubAgentProfile:
        """
        Resolve a SubAgentProfile by id, display_name, normalized name, or phonetic alias.

        Raises KeyError if no matching profile exists.
        """

    @abstractmethod
    def register_profile(self, profile: SubAgentProfile) -> None:
        """Register or replace (matching by id) a SubAgentProfile."""

    @abstractmethod
    def unregister_profile(self, identifier: str) -> bool:
        """Unregister a profile matching identifier. Returns False if not found."""


class ITopologyProvider(ABC):
    """Port for obtaining the validated DebateTopology configuration."""

    @abstractmethod
    def get_topology(self) -> DebateTopology:
        """Return the active DebateTopology."""

