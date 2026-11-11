"""
Domain Port: IModelCacheRepository

Defines the interface for storing and retrieving provider model catalogs
across distributed backend instances, with atomic probe locking to prevent
duplicate probing across cluster replicas (ADR-021, ADR-024).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class CachedModelCatalog:
    provider: str
    models: list[dict[str, str]]
    is_verified: bool
    updated_at: float
    app_version: str


class IModelCacheRepository(Protocol):
    def get(self, provider: str) -> Optional[CachedModelCatalog]:
        """Retrieve the cached model catalog for a provider."""
        ...

    def save(self, catalog: CachedModelCatalog) -> None:
        """Persist or update the model catalog for a provider."""
        ...

    def acquire_probe_lock(self, provider: str, timeout_seconds: float = 60.0) -> bool:
        """
        Atomically acquire a distributed probe lock for this provider.
        Returns True if this replica acquired the lock, False if another replica is probing.
        """
        ...

    def release_probe_lock(self, provider: str) -> None:
        """Release the probe lock for this provider."""
        ...

    def invalidate_all(self) -> None:
        """Purge all cached model entries (e.g. on manual refresh or deployment reset)."""
        ...

