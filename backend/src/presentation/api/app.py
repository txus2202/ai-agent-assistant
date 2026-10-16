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
    settings = get_settings()
    # Validate config early (will raise if default_provider is invalid)
    _ = settings.default_provider
    
    # Initialize SQLite repositories to ensure schemas are created
    db_path = str(settings.sqlite_db_path)
    SqliteAgentConfigRepository(db_path)
    SqliteDebateRepository(db_path)
    
    # Ensure Langfuse Docker stack matches LANGFUSE_METRICS_ENABLED
    docker_manager = DockerObservabilityManager()
    await asyncio.to_thread(docker_manager.ensure_stack_state, settings.langfuse_metrics_enabled)
    
    # Future: ChromaDB, LLMProviderRegistry init
    yield
    # ── Shutdown ─────────────────────────────────────────────────────────
    if settings.langfuse_metrics_enabled:
        await asyncio.to_thread(docker_manager.stop_stack)



def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="A.T.E.N.E.A.",
        description="AI Architecture Assistant — Multi-Agent Debate API",
        version=settings.api_version,
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ──────────────────────────────────────────────────────────
    from src.presentation.api.routes import health, config, upload, history, models, audio, observability
    from src.presentation.api.ws import debate, wake_word

    # Register routes
    app.include_router(health.router)
    app.include_router(config.router)
    app.include_router(upload.router)
    app.include_router(history.router)
    app.include_router(models.router)
    app.include_router(audio.router)
    app.include_router(observability.router)
    app.include_router(debate.router)
    app.include_router(wake_word.router)
    
    # Future routers registered here as they are implemented:
    # app.include_router(settings_router, prefix="/settings")
    # app.include_router(learn_router,    prefix="/learn")
    # app.include_router(history_router,  prefix="/debates")

    return app


# Module-level instance for uvicorn: `uvicorn src.presentation.api.app:app`
app = create_app()
