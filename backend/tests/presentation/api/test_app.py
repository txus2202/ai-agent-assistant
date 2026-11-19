"""
Tests — FastAPI Server Bootstrap (feature_fastapi_server.md)

Layer: Presentation

Strategy:
  - httpx.AsyncClient with ASGITransport (no real server started)
  - Settings overridden via environment variables
  - Each test class uses its own app instance via create_app()

Scenarios:
  1. GET /health returns 200 { status: ok, version }
  2. CORS headers present for allowed origin
  3. CORS headers absent for unknown origin
  4. Server starts without API keys configured
  5. Unknown route returns 404
  6. Settings default_provider validates at startup
"""
from __future__ import annotations

import os

import pytest
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(env_overrides: dict | None = None):
    """
    Returns an async context manager wrapping AsyncClient against the ASGI app.
    Resets the settings singleton before creating the app so env vars take effect.
    """
    import contextlib

    @contextlib.asynccontextmanager
    async def _ctx():
        # Reset singleton so test env vars are picked up
        from src.presentation.api import config as cfg_mod
        cfg_mod.reset_settings()

        from src.presentation.api.app import create_app
        test_app = create_app()

        async with AsyncClient(
            transport=ASGITransport(app=test_app),
            base_url="http://testserver",
        ) as client:
            yield client

        # Cleanup
        cfg_mod.reset_settings()

    return _ctx()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHealth:
    @pytest.mark.anyio
    async def test_health_returns_200(self):
        async with _make_client() as client:
            response = await client.get("/health")
        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_health_returns_status_ok(self):
        async with _make_client() as client:
            response = await client.get("/health")
        body = response.json()
        assert body["status"] == "ok"

    @pytest.mark.anyio
    async def test_health_returns_version(self):
        async with _make_client() as client:
            response = await client.get("/health")
        body = response.json()
        assert "version" in body
        assert len(body["version"]) > 0

    @pytest.mark.anyio
    async def test_unknown_route_returns_404(self):
        async with _make_client() as client:
            response = await client.get("/this-does-not-exist")
        assert response.status_code == 404


class TestCORS:
    @pytest.mark.anyio
    async def test_cors_headers_present_for_allowed_origin(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", '["http://localhost:5173"]')
        async with _make_client() as client:
            response = await client.options(
                "/health",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "GET",
                },
            )
        assert "access-control-allow-origin" in response.headers

    @pytest.mark.anyio
    async def test_cors_allows_localhost_5173_by_default(self):
        """Default cors_origins includes localhost:5173 — no env override needed."""
        async with _make_client() as client:
            response = await client.get(
                "/health",
                headers={"Origin": "http://localhost:5173"},
            )
        # When origin is allowed, the header is echoed back
        assert response.headers.get("access-control-allow-origin") in (
            "http://localhost:5173",
            "*",
        )


class TestStartupWithoutKeys:
    @pytest.mark.anyio
    async def test_server_starts_without_api_keys(self, monkeypatch):
        """Keys are validated at request time, not startup — server must start clean."""
        monkeypatch.setenv("GEMINI_API_KEY", "")
        monkeypatch.setenv("OPENAI_API_KEY", "")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        async with _make_client() as client:
            response = await client.get("/health")
        assert response.status_code == 200


class TestSettingsEnvAlignment:
    def test_settings_uses_canonical_env_vars_with_legacy_aliases(self, monkeypatch):
        from src.presentation.api.config import Settings

        monkeypatch.setenv("SQLITE_DB_PATH", "/tmp/canonical.db")
        monkeypatch.setenv("DB_PATH", "/tmp/legacy.db")
        monkeypatch.setenv("CHROMA_PERSIST_DIR", "/tmp/canonical_chroma")
        monkeypatch.setenv("CHROMA_PATH", "/tmp/legacy_chroma")
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "canonical-gcp")
        monkeypatch.setenv("VERTEX_PROJECT_ID", "legacy-gcp")

        cfg = Settings(_env_file=None)
        assert str(cfg.sqlite_db_path) == "/tmp/canonical.db"
        assert str(cfg.chroma_persist_dir) == "/tmp/canonical_chroma"
        assert cfg.google_cloud_project == "canonical-gcp"

    def test_settings_falls_back_to_legacy_db_and_chroma_path_aliases(self, monkeypatch):
        from src.presentation.api.config import Settings

        monkeypatch.delenv("SQLITE_DB_PATH", raising=False)
        monkeypatch.delenv("CHROMA_PERSIST_DIR", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        monkeypatch.setenv("DB_PATH", "/tmp/legacy_only.db")
        monkeypatch.setenv("CHROMA_PATH", "/tmp/legacy_only_chroma")
        monkeypatch.setenv("VERTEX_PROJECT_ID", "legacy-vertex-project")

        cfg = Settings(_env_file=None)
        assert str(cfg.sqlite_db_path) == "/tmp/legacy_only.db"
        assert str(cfg.chroma_persist_dir) == "/tmp/legacy_only_chroma"
        assert cfg.google_cloud_project == "legacy-vertex-project"

    def test_settings_default_model_and_database_url(self, monkeypatch):
        from src.presentation.api.config import Settings

        monkeypatch.delenv("DEFAULT_MODEL", raising=False)
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@postgres:5432/atenea")

        cfg = Settings(_env_file=None)
        assert cfg.default_model == "gemini-3.6-flash"
        assert cfg.database_url == "postgresql://user:pass@postgres:5432/atenea"


class TestLifespanDecoupling:
    def test_app_module_does_not_manage_docker_lifecycle(self):
        import inspect
        from src.presentation.api import app as app_mod

        source = inspect.getsource(app_mod)
        assert "DockerObservabilityManager" not in source
        assert "atexit" not in source

    @pytest.mark.anyio
    async def test_init_postgres_pool_retries_transient_os_error(self, monkeypatch):
        import sys
        import types
        from unittest.mock import AsyncMock, MagicMock
        from fastapi import FastAPI
        from src.presentation.api.app import _init_postgres_pool

        attempts = 0
        mock_pool = MagicMock()

        async def _flaky_create_pool(dsn: str):
            nonlocal attempts
            attempts += 1
            if attempts < 2:
                raise OSError("postgres starting")
            return mock_pool

        fake_asyncpg = types.ModuleType("asyncpg")
        fake_asyncpg.create_pool = _flaky_create_pool  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "asyncpg", fake_asyncpg)

        mock_pg_repo = MagicMock()
        mock_pg_repo.init_schema = AsyncMock()
        monkeypatch.setattr(
            "src.infrastructure.persistence.postgres_user_repository.PostgreSQLUserRepository",
            lambda pool: mock_pg_repo,
        )

        test_app = FastAPI()
        await _init_postgres_pool(test_app, "postgresql://user:pass@postgres:5432/atenea", max_attempts=3, retry_delay=0.0)
        assert attempts == 2
        assert test_app.state.db_pool is mock_pool
        mock_pg_repo.init_schema.assert_awaited_once()


class TestAsyncEventLoopNonBlocking:
    @pytest.mark.anyio
    async def test_health_remains_responsive_during_slow_learning_request(self, monkeypatch, tmp_path):
        import asyncio
        import threading
        import time
        from unittest.mock import MagicMock
        from src.application.services.learn_from_session import LearnFromSession
        from src.application.services.learn_from_source import LearnResult
        from src.application.services.ingest_vault import IngestResult
        from src.domain.entities.user import User
        from src.domain.ports.document_store import IDocumentStore
        from src.presentation.api.app import create_app
        from src.presentation.api.config import Settings
        from src.presentation.api.dependencies.auth import get_current_user

        main_tid = threading.get_ident()
        entered_worker = asyncio.Event()
        release_worker = threading.Event()
        loop = asyncio.get_running_loop()
        worker_tid: list[int] = []

        def _slow_learn_run(**kwargs):
            worker_tid.append(threading.get_ident())
            loop.call_soon_threadsafe(entered_worker.set)
            release_worker.wait(timeout=2.0)
            return LearnResult(
                source="slow-session",
                generated_file=tmp_path / "learned" / "slow.md",
                ingest_result=IngestResult(files_processed=1, chunks_upserted=1),
                errors=[],
            )

        monkeypatch.setattr("src.presentation.api.routes.learning.get_llm_provider", lambda _prov, **_kw: MagicMock())
        monkeypatch.setattr(LearnFromSession, "run", staticmethod(_slow_learn_run))

        settings = Settings(
            sqlite_db_path=tmp_path / "app.db",
            vault_path=tmp_path / "vault",
            auth_secret_key="test_secret_key_32_bytes_minimum_length",
        )
        fake_store = MagicMock(spec=IDocumentStore)
        test_app = create_app(settings=settings, document_store=fake_store)
        test_app.dependency_overrides[get_current_user] = lambda: User(
            id="usr-async", username="tester", password_hash="h", is_admin=False
        )

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://testserver") as client:
            slow_task = asyncio.create_task(
                client.post(
                    "/learning/session",
                    json={"session_id": "slow-session", "content": "Architecture consensus notes"},
                )
            )
            await asyncio.wait_for(entered_worker.wait(), timeout=2.0)

            t0 = time.perf_counter()
            health_resp = await client.get("/health")
            health_elapsed = time.perf_counter() - t0
            release_worker.set()
            learn_resp = await slow_task

        assert health_resp.status_code == 200
        assert health_elapsed < 0.1
        assert learn_resp.status_code == 200
        assert worker_tid and worker_tid[0] != main_tid
