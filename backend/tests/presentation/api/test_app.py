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
