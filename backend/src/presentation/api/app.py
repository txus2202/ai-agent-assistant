"""
Presentation: FastAPI application factory

create_app() returns a configured FastAPI instance.
Using a factory (not a module-level `app`) makes the app
testable without starting a real server (httpx.AsyncClient).

Lifespan:
  startup  → initialise shared resources (settings validated, future: DB, registry)
  shutdown → teardown

CORS is configured from Settings.cors_origins.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from src.presentation.api.config import Settings, get_settings
from src.infrastructure.persistence.sqlite_agent_config_repository import SqliteAgentConfigRepository
from src.infrastructure.persistence.sqlite_debate_repository import SqliteDebateRepository

if TYPE_CHECKING:
    from src.application.services.llm_provider_registry import LLMProviderRegistry
    from src.domain.ports.agent_catalog_repository import (
        IAgentCatalogRepository,
        ITopologyProvider,
    )
    from src.domain.ports.document_parser import IDocumentParser
    from src.domain.ports.document_store import IDocumentStore
    from src.domain.ports.image_generator import IImageGenerator
    from src.domain.ports.source_extractor import ISourceExtractor, SourceType
    from src.infrastructure.llm.registry import LLMProviderConfig

logger = logging.getLogger(__name__)


async def _init_postgres_pool(
    app: FastAPI,
    db_url: str,
    max_attempts: int = 5,
    retry_delay: float = 1.5,
) -> None:
    """Initialize asyncpg pool with bounded retries for `--profile scale` startup ordering."""
    try:
        import asyncpg
    except ImportError:
        raise RuntimeError(
            f"DATABASE_URL is set to '{db_url}', but asyncpg is not installed. "
            "Install it with `pip install asyncpg` or unset DATABASE_URL to use SQLite."
        )

    from src.infrastructure.persistence.postgres_user_repository import PostgreSQLUserRepository

    for attempt in range(1, max_attempts + 1):
        try:
            app.state.db_pool = await asyncpg.create_pool(dsn=db_url)
            pg_repo = PostgreSQLUserRepository(pool=app.state.db_pool)
            await pg_repo.init_schema()
            return
        except OSError as exc:
            if attempt >= max_attempts:
                raise
            logger.warning(
                "PostgreSQL not ready on attempt %d/%d (%s); retrying in %.1fs...",
                attempt,
                max_attempts,
                exc,
                retry_delay,
            )
            await asyncio.sleep(retry_delay)


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    # ── Startup ──────────────────────────────────────────────────────────
    settings = getattr(app.state, "settings", None) or get_settings()
    # Validate config early (will raise if default_provider or auth_secret_key is invalid)
    _ = settings.default_provider
    from src.infrastructure.security.jwt_token_service import JwtTokenService
    JwtTokenService(secret_key=settings.auth_secret_key, default_expiry_seconds=settings.auth_token_expiry_seconds)
    
    # Initialize SQLite repositories to ensure schemas are created
    db_path = str(settings.sqlite_db_path)
    SqliteAgentConfigRepository(db_path)
    SqliteDebateRepository(db_path)
    from src.infrastructure.persistence.sqlite_user_repository import SQLiteUserRepository
    SQLiteUserRepository(db_path)
    from src.infrastructure.persistence.sqlite_model_cache_repository import SqliteModelCacheRepository
    SqliteModelCacheRepository(db_path, app_version=getattr(settings, "api_version", "0.4.0"))

    # Initialize PostgreSQL pool if configured
    db_url = getattr(settings, "database_url", "")
    if db_url and db_url.startswith(("postgres://", "postgresql://")):
        await _init_postgres_pool(app, db_url)
    
    # Warm and validate agent catalog + debate topology in composition root
    from src.presentation.api.dependencies.agents import (
        build_agent_catalog_repository,
        build_topology_provider,
    )
    if getattr(app.state, "agent_catalog", None) is None:
        app.state.agent_catalog = build_agent_catalog_repository(settings)
    if getattr(app.state, "topology_provider", None) is None:
        app.state.topology_provider = build_topology_provider(
            settings,
            agent_catalog=app.state.agent_catalog,
        )
    app.state.topology_provider.get_topology()

    from src.presentation.api.dependencies.llm import (
        build_llm_provider_config,
        build_llm_provider_registry,
    )
    if getattr(app.state, "llm_config", None) is None:
        app.state.llm_config = build_llm_provider_config(settings)
    if getattr(app.state, "llm_registry", None) is None:
        app.state.llm_registry = build_llm_provider_registry(
            settings,
            config=app.state.llm_config,
        )
    try:
        yield
    finally:
        # ── Shutdown ─────────────────────────────────────────────────────────
        if hasattr(app.state, "db_pool") and app.state.db_pool:
            await app.state.db_pool.close()



def create_app(
    settings: Settings | None = None,
    auth_service: Any = None,
    document_store: IDocumentStore | None = None,
    agent_catalog: IAgentCatalogRepository | None = None,
    topology_provider: ITopologyProvider | None = None,
    llm_config: LLMProviderConfig | None = None,
    llm_registry: LLMProviderRegistry | None = None,
    image_generator: IImageGenerator | None = None,
    document_parser: IDocumentParser | None = None,
    source_extractors: dict[SourceType, ISourceExtractor] | None = None,
) -> FastAPI:
    cfg = settings or get_settings()

    app = FastAPI(
        title="A.T.E.N.E.A.",
        description="AI Architecture Assistant — Multi-Agent Debate API",
        version=cfg.api_version,
        lifespan=lifespan,
    )
    from src.presentation.api.dependencies.agents import (
        build_agent_catalog_repository,
        build_topology_provider,
    )
    from src.presentation.api.dependencies.learning import build_source_extractors
    from src.presentation.api.dependencies.llm import (
        build_image_generator,
        build_llm_provider_config,
        build_llm_provider_registry,
    )
    from src.presentation.api.dependencies.rag import build_document_parser

    resolved_catalog = agent_catalog or build_agent_catalog_repository(cfg)
    resolved_topology_provider = topology_provider or build_topology_provider(
        cfg,
        agent_catalog=resolved_catalog,
    )
    resolved_llm_config = llm_config if llm_config is not None else build_llm_provider_config(cfg)
    resolved_llm_registry = (
        llm_registry
        if llm_registry is not None
        else build_llm_provider_registry(cfg, config=resolved_llm_config)
    )

    app.state.settings = cfg
    app.state.document_store = document_store
    app.state.agent_catalog = resolved_catalog
    app.state.topology_provider = resolved_topology_provider
    app.state.llm_config = resolved_llm_config
    app.state.llm_registry = resolved_llm_registry
    app.state.image_generator = image_generator if image_generator is not None else build_image_generator(cfg)
    app.state.document_parser = document_parser if document_parser is not None else build_document_parser()
    app.state.source_extractors = (
        source_extractors if source_extractors is not None else build_source_extractors()
    )
    if auth_service is not None:
        app.state.auth_service = auth_service

    # ── CORS ─────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cfg.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ──────────────────────────────────────────────────────────
    from src.presentation.api.routes import health, config, upload, history, models, audio, observability, learning, images, auth
    from src.presentation.api.ws import debate, wake_word

    # Register REST routers uniformly at root (behind Nginx/Vite stripping /api) and /api
    for rest_router in (
        health.router,
        auth.router,
        config.router,
        upload.router,
        images.router,
        history.router,
        models.router,
        audio.router,
        observability.router,
        learning.router,
    ):
        app.include_router(rest_router)
        app.include_router(rest_router, prefix="/api", include_in_schema=False)

    app.include_router(debate.router)
    app.include_router(wake_word.router)

    
    # Future routers registered here as they are implemented:
    # app.include_router(settings_router, prefix="/settings")
    # app.include_router(learn_router,    prefix="/learn")
    # app.include_router(history_router,  prefix="/debates")

    return app


# Module-level instance for uvicorn: `uvicorn src.presentation.api.app:app`
app = create_app()
