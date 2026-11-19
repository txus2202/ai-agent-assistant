import time

import pytest
from fastapi.testclient import TestClient

from src.application.services.llm_provider_registry import LLMProviderRegistry
from src.domain.entities.user import User
from src.domain.ports.model_cache_repository import CachedModelCatalog
from src.infrastructure.persistence.sqlite_model_cache_repository import SqliteModelCacheRepository
from src.presentation.api.app import create_app
from src.presentation.api.dependencies.auth import get_current_user
from src.presentation.api.dependencies.llm import get_llm_registry
from src.presentation.api.dependencies.model_cache import get_model_cache_repository


@pytest.fixture
def test_user():
    return User(
        id="test-user-id",
        username="testadmin",
        password_hash="fakehash",
        is_admin=True,
        is_active=True,
    )


@pytest.fixture
def shared_cache_repo(tmp_path):
    db_path = str(tmp_path / "test_shared_models.db")
    return SqliteModelCacheRepository(db_path, app_version="0.4.0")


@pytest.fixture
def client(test_user, shared_cache_repo):
    app = create_app(llm_registry=LLMProviderRegistry())
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_model_cache_repository] = lambda: shared_cache_repo
    return TestClient(app)


def _registry_with(name: str, adapter) -> LLMProviderRegistry:
    registry = LLMProviderRegistry()
    registry.register(name, adapter)
    return registry


def test_cold_start_swr_returns_preliminary_and_executes_probe(client, shared_cache_repo):
    calls = []

    class FakeGemini:
        def complete(self, prompt: str, model_name: str) -> str:
            return "ok"

        def list_models(self, probe: bool = True):
            calls.append(probe)
            if not probe:
                return [
                    {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"},
                    {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash"},
                ]
            return [{"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"}]

    client.app.dependency_overrides[get_llm_registry] = lambda: _registry_with("gemini", FakeGemini())

    # 1. Cold start request returns preliminary list immediately and runs background probe
    res = client.get("/models")
    assert res.status_code == 200
    assert res.headers.get("x-models-probing") == "1"
    data = res.json()
    assert len(data[0]["models"]) == 2  # Preliminary unverified returned fast
    assert False in calls  # Fast unprobed call executed

    # Background task ran at response completion
    assert True in calls  # Probing completed
    verified = shared_cache_repo.get("gemini")
    assert verified is not None
    assert verified.is_verified is True
    assert len(verified.models) == 1

    # 2. Next request returns verified probed cache immediately (<2ms) without re-probing
    calls.clear()
    res2 = client.get("/models")
    assert res2.status_code == 200
    assert res2.headers.get("x-models-probing") == "0"
    data2 = res2.json()
    assert len(data2[0]["models"]) == 1
    assert calls == []  # No adapter calls, served purely from shared DB!


def test_multi_pod_simulation_avoids_duplicate_probing(test_user, shared_cache_repo):
    """
    Simulates Pod 1 and Pod 2 sharing the same database.
    When Pod 1 acquires the probe lock, Pod 2 serves the existing catalog without firing a duplicate probe.
    """
    gemini_probes = 0

    class FakeGemini:
        def complete(self, prompt: str, model_name: str) -> str:
            return "ok"

        def list_models(self, probe: bool = True):
            nonlocal gemini_probes
            if probe:
                gemini_probes += 1
            return [{"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"}]

    registry = _registry_with("gemini", FakeGemini())

    app2 = create_app(llm_registry=registry)
    app2.dependency_overrides[get_current_user] = lambda: test_user
    app2.dependency_overrides[get_model_cache_repository] = lambda: shared_cache_repo
    client2 = TestClient(app2)

    # Seed shared DB with lock held by another pod
    shared_cache_repo.save(CachedModelCatalog(
        provider="gemini",
        models=[{"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"}],
        is_verified=False,
        updated_at=time.time() - 90000.0,  # Stale
        app_version="0.4.0",
    ))
    shared_cache_repo.acquire_probe_lock("gemini", timeout_seconds=60.0)

    # Pod 2 receives a request while Pod 1 holds lock
    res_pod2 = client2.get("/models")
    assert res_pod2.status_code == 200
    assert len(res_pod2.json()[0]["models"]) == 1
    # Pod 2 did NOT execute probe because lock was held by Pod 1!
    assert gemini_probes == 0


def test_refresh_query_param_invalidates_shared_cache(client, shared_cache_repo):
    shared_cache_repo.save(CachedModelCatalog(
        provider="gemini",
        models=[{"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"}],
        is_verified=True,
        updated_at=time.time(),
        app_version="0.4.0",
    ))

    probe_called = False

    class FakeGemini:
        def complete(self, prompt: str, model_name: str) -> str:
            return "ok"

        def list_models(self, probe: bool = True):
            nonlocal probe_called
            if probe:
                probe_called = True
            return [{"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"}]

    client.app.dependency_overrides[get_llm_registry] = lambda: _registry_with("gemini", FakeGemini())

    res = client.get("/models?refresh=true")
    assert res.status_code == 200
    assert probe_called is True


def test_unconfigured_providers_are_never_attempted_or_probed(client):
    """Verifies that providers absent from LLMProviderRegistry are skipped completely."""

    class FakeGemini:
        def complete(self, prompt: str, model_name: str) -> str:
            return "ok"

        def list_models(self, probe: bool = True):
            return [{"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"}]

    registry = _registry_with("gemini", FakeGemini())
    client.app.dependency_overrides[get_llm_registry] = lambda: registry

    res = client.get("/models")
    assert res.status_code == 200
    data = res.json()

    assert len(data) == 1
    assert data[0]["id"] == "gemini"
    assert registry.available() == ["gemini"]
