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
