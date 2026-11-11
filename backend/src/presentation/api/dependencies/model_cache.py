"""
Presentation Dependency: Model Cache Repository

Provides the shared IModelCacheRepository instance configured according
to application settings.
"""
from __future__ import annotations

from functools import lru_cache

from src.domain.ports.model_cache_port import IModelCacheRepository
from src.infrastructure.persistence.sqlite_model_cache_repository import SqliteModelCacheRepository
from src.presentation.api.config import get_settings


@lru_cache(maxsize=1)
def get_model_cache_repository() -> IModelCacheRepository:
    settings = get_settings()
    return SqliteModelCacheRepository(
        db_path=str(settings.sqlite_db_path),
        app_version=getattr(settings, "api_version", "0.4.0"),
    )

