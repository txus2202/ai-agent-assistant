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
import atexit
import os
import sys

from src.presentation.api.config import get_settings
from src.infrastructure.persistence.sqlite_agent_config_repository import SqliteAgentConfigRepository
from src.infrastructure.persistence.sqlite_debate_repository import SqliteDebateRepository
from src.infrastructure.observability.docker_manager import DockerObservabilityManager


def _cleanup_docker_on_exit() -> None:
    """Safety fallback to ensure Docker stack stops when the Python process exits."""
    if "pytest" in sys.modules or os.environ.get("ENV") == "test":
        return
    try:
        settings = get_settings()
        if settings.langfuse_metrics_enabled:
            DockerObservabilityManager().stop_stack()
    except Exception:
        pass


atexit.register(_cleanup_docker_on_exit)


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
        try:
            import asyncpg
            app.state.db_pool = await asyncpg.create_pool(dsn=db_url)
            from src.infrastructure.persistence.postgres_user_repository import PostgreSQLUserRepository
            pg_repo = PostgreSQLUserRepository(pool=app.state.db_pool)
            await pg_repo.init_schema()
        except ImportError:
            raise RuntimeError(
                f"DATABASE_URL is set to '{db_url}', but asyncpg is not installed. "
                "Install it with `pip install asyncpg` or unset DATABASE_URL to use SQLite."
            )
    
    # Ensure Langfuse Docker stack matches LANGFUSE_METRICS_ENABLED
    docker_manager = DockerObservabilityManager()
    await asyncio.to_thread(docker_manager.ensure_stack_state, settings.langfuse_metrics_enabled)
    
    # Future: ChromaDB, LLMProviderRegistry init
    try:
        yield
    finally:
        # ── Shutdown ─────────────────────────────────────────────────────────
        if hasattr(app.state, "db_pool") and app.state.db_pool:
            await app.state.db_pool.close()
        if settings.langfuse_metrics_enabled:
            await asyncio.to_thread(docker_manager.stop_stack)



def create_app(
    settings: Settings | None = None,
    auth_service: Any = None,
) -> FastAPI:
    cfg = settings or get_settings()

    app = FastAPI(
        title="A.T.E.N.E.A.",
        description="AI Architecture Assistant — Multi-Agent Debate API",
        version=cfg.api_version,
        lifespan=lifespan,
    )
    app.state.settings = cfg
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
