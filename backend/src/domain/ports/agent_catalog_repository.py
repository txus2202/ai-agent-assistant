"""
Domain Ports: Agent Catalog & Debate Topology

Defines pure abstractions for retrieving agent profile catalogs and multi-agent
debate topologies without coupling domain/application layers to YAML or filesystem I/O.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.agents.debate_topology import DebateTopology
from src.domain.agents.sub_agent_profiles import SubAgentProfile


@runtime_checkable
class IAgentCatalogRepository(Protocol):
    """Port for querying and managing registered SubAgentProfile definitions."""

    def get_all_profiles(self) -> list[SubAgentProfile]:
        """Return all registered SubAgentProfile instances in registration order."""
        ...

    def get_profile(self, identifier: str) -> SubAgentProfile:
        """
        Resolve a SubAgentProfile by id, display_name, normalized name, or phonetic alias.

        Raises KeyError if no matching profile exists.
        """
        ...

    def register_profile(self, profile: SubAgentProfile) -> None:
        """Register or replace (matching by id) a SubAgentProfile."""
        ...

    def unregister_profile(self, identifier: str) -> bool:
        """Unregister a profile matching identifier. Returns False if not found."""
        ...


@runtime_checkable
class ITopologyProvider(Protocol):
    """Port for obtaining the validated DebateTopology configuration."""

    def get_topology(self) -> DebateTopology:
        """Return the active DebateTopology."""
        ...
