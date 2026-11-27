"""
Composition Root Dependencies: Agent Catalog & Debate Topology

Wires infrastructure YAML catalog/topology adapters and caches immutable YAML parsing
while giving each application instance an isolated repository instance.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from fastapi import Depends
from starlette.requests import HTTPConnection

from src.domain.agents.sub_agent_profiles import SubAgentProfile
from src.domain.ports.agent_catalog_repository import (
    IAgentCatalogRepository,
    ITopologyProvider,
)
from src.domain.ports.user_topology_repository import IUserTopologyRepository
from src.application.services.user_topology_service import UserTopologyService
from src.infrastructure.config.yaml_agent_catalog import (
    InMemoryAgentCatalogRepository,
    default_agents_file,
    load_profiles_from_file,
)
from src.infrastructure.config.yaml_topology_provider import (
    YamlTopologyProvider,
    resolve_topology_path,
)
from src.infrastructure.persistence.sqlite_user_topology_repository import (
    SqliteUserTopologyRepository,
)
from src.presentation.api.config import Settings, get_settings


@lru_cache(maxsize=8)
def _load_cached_yaml_profiles(resolved_path: str) -> tuple[SubAgentProfile, ...]:
    """Read and validate agents.yaml once per canonical file path."""
    return tuple(load_profiles_from_file(resolved_path))


def _resolve_agents_path(settings: Settings | None = None) -> Path:
    configured = getattr(settings, "agents_file", None) if settings is not None else None
    if configured:
        return Path(configured)
    return default_agents_file()


def _resolve_topology_file(settings: Settings | None = None) -> Path:
    configured = getattr(settings, "topology_file", None) if settings is not None else None
    return resolve_topology_path(configured)


def build_agent_catalog_repository(
    settings: Settings | None = None,
) -> IAgentCatalogRepository:
    """Build an isolated IAgentCatalogRepository backed by cached YAML profile definitions."""
    cfg = settings or get_settings()
    resolved = str(_resolve_agents_path(cfg).resolve())
    profiles = _load_cached_yaml_profiles(resolved)
    return InMemoryAgentCatalogRepository(profiles=profiles)


def build_topology_provider(
    settings: Settings | None = None,
    *,
    agent_catalog: IAgentCatalogRepository | None = None,
) -> ITopologyProvider:
    """Build a YamlTopologyProvider bound to the provided or configured agent catalog."""
    cfg = settings or get_settings()
    catalog = agent_catalog if agent_catalog is not None else build_agent_catalog_repository(cfg)
    top_path = _resolve_topology_file(cfg)
    return YamlTopologyProvider(agent_catalog=catalog, topology_path=top_path)


def get_agent_catalog(
    connection: HTTPConnection,
    settings: Settings = Depends(get_settings),
) -> IAgentCatalogRepository:
    """FastAPI dependency resolving IAgentCatalogRepository from app.state or building it."""
    app_state = getattr(getattr(connection, "app", None), "state", None)
    existing = getattr(app_state, "agent_catalog", None) if app_state is not None else None
    if existing is not None:
        return existing
    catalog = build_agent_catalog_repository(getattr(app_state, "settings", None) or settings)
    if app_state is not None:
        app_state.agent_catalog = catalog
    return catalog


def get_topology_provider(
    connection: HTTPConnection,
    settings: Settings = Depends(get_settings),
) -> ITopologyProvider:
    """FastAPI dependency resolving ITopologyProvider from app.state or building it."""
    app_state = getattr(getattr(connection, "app", None), "state", None)
    existing = getattr(app_state, "topology_provider", None) if app_state is not None else None
    if existing is not None:
        return existing
    catalog = get_agent_catalog(connection, settings)
    provider = build_topology_provider(
        getattr(app_state, "settings", None) or settings,
        agent_catalog=catalog,
    )
    if app_state is not None:
        app_state.topology_provider = provider
    return provider


def clear_agent_config_caches() -> None:
    """Clear cached YAML profile definitions (used in tests after rewriting fixtures)."""
    _load_cached_yaml_profiles.cache_clear()


def resolve_effective_settings(
    connection: HTTPConnection | None = None,
    fallback: Settings | None = None,
) -> Settings:
    """Resolve app.state.settings when injected into create_app(), falling back to get_settings()."""
    app_state = getattr(getattr(connection, "app", None), "state", None) if connection is not None else None
    state_settings = getattr(app_state, "settings", None) if app_state is not None else None
    return state_settings or fallback or get_settings()


def resolve_fallback_review_rounds(settings: Settings) -> int | None:
    """Return explicit REVIEW_ROUNDS override from Settings only when explicitly set."""
    if "review_rounds" in settings.model_fields_set:
        return settings.review_rounds
    return None


def get_user_topology_repository(
    connection: HTTPConnection,
    settings: Settings = Depends(get_settings),
) -> IUserTopologyRepository:
    """FastAPI dependency providing SqliteUserTopologyRepository bound to active app settings."""
    cfg = resolve_effective_settings(connection, settings)
    return SqliteUserTopologyRepository(db_path=str(cfg.sqlite_db_path))


def get_user_topology_service(
    connection: HTTPConnection,
    settings: Settings = Depends(get_settings),
) -> UserTopologyService:
    """FastAPI dependency providing UserTopologyService wired with catalog, YAML base, and SQLite overrides."""
    catalog = get_agent_catalog(connection, settings)
    provider = get_topology_provider(connection, settings)
    repo = get_user_topology_repository(connection, settings)
    return UserTopologyService(
        agent_catalog=catalog,
        topology_provider=provider,
        user_topology_repo=repo,
    )

