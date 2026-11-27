"""
Domain Port: IUserTopologyRepository

Defines persistence operations for per-operator debate topology overrides
without coupling Domain or Application layers to SQLite or PostgreSQL.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.domain.value_objects.user_topology_config import UserTopologyConfig


@runtime_checkable
class IUserTopologyRepository(Protocol):
    """Port for persisting and retrieving per-user debate topology preferences."""

    def find_by_user_id(self, user_id: str) -> UserTopologyConfig | None:
        """Return the saved UserTopologyConfig for ``user_id``, or None if uncustomized."""
        ...

    def save(self, config: UserTopologyConfig) -> None:
        """Persist or replace the topology override for ``config.user_id``."""
        ...

    def delete_by_user_id(self, user_id: str) -> None:
        """Delete any saved topology override for ``user_id``."""
        ...

