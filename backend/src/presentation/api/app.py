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

from src.presentation.api.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    # ── Startup ──────────────────────────────────────────────────────────
    settings = get_settings()
    # Validate config early (will raise if default_provider is invalid)
    _ = settings.default_provider
    # Future: ChromaDB, SQLite connection pool, LLMProviderRegistry init
    yield
    # ── Shutdown ─────────────────────────────────────────────────────────
    # Future: close DB connections


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
    from src.presentation.api.routes import health, config
    from src.presentation.api.ws import debate

    # Register routes
    app.include_router(health.router)
    app.include_router(config.router)
    app.include_router(debate.router)
    
    # Future routers registered here as they are implemented:
    # app.include_router(settings_router, prefix="/settings")
    # app.include_router(models_router,   prefix="/models")
    # app.include_router(learn_router,    prefix="/learn")
    # app.include_router(history_router,  prefix="/debates")

    return app


# Module-level instance for uvicorn: `uvicorn src.presentation.api.app:app`
app = create_app()
