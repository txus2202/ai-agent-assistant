import pytest
import time
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from src.presentation.api.app import create_app
from src.domain.entities.user import User
from src.domain.ports.model_cache_port import CachedModelCatalog
from src.infrastructure.persistence.sqlite_model_cache_repository import SqliteModelCacheRepository
from src.presentation.api.dependencies.auth import get_current_user
from src.presentation.api.dependencies.model_cache import get_model_cache_repository
import src.presentation.api.routes.models as models_module

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
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: test_user
    app.dependency_overrides[get_model_cache_repository] = lambda: shared_cache_repo
    return TestClient(app)


def test_cold_start_swr_returns_preliminary_and_executes_probe(client, shared_cache_repo, monkeypatch):
    calls = []

    class FakeGemini:
        def list_models(self, probe: bool = True):
            calls.append(probe)
            if not probe:
                return [
                    {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"},
                    {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash"},
                ]
            return [{"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"}]

    monkeypatch.setattr(
        models_module,
        "get_llm_provider",
        lambda name: FakeGemini() if name == "gemini" else (_ for _ in ()).throw(RuntimeError("N/A")),
    )

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


def test_multi_pod_simulation_avoids_duplicate_probing(test_user, shared_cache_repo, monkeypatch):
    """
    Simulates Pod 1 and Pod 2 sharing the same database.
    When Pod 1 acquires the probe lock, Pod 2 serves the existing catalog without firing a duplicate probe.
    """
    app1 = create_app()
    app1.dependency_overrides[get_current_user] = lambda: test_user
    app1.dependency_overrides[get_model_cache_repository] = lambda: shared_cache_repo
    client1 = TestClient(app1)

    app2 = create_app()
    app2.dependency_overrides[get_current_user] = lambda: test_user
    app2.dependency_overrides[get_model_cache_repository] = lambda: shared_cache_repo
    client2 = TestClient(app2)

    gemini_probes = 0

    class FakeGemini:
        def list_models(self, probe: bool = True):
            nonlocal gemini_probes
            if probe:
                gemini_probes += 1
            return [{"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"}]

    monkeypatch.setattr(
        models_module,
        "get_llm_provider",
        lambda name: FakeGemini() if name == "gemini" else (_ for _ in ()).throw(RuntimeError("N/A")),
    )

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


def test_refresh_query_param_invalidates_shared_cache(client, shared_cache_repo, monkeypatch):
    shared_cache_repo.save(CachedModelCatalog(
        provider="gemini",
        models=[{"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"}],
        is_verified=True,
        updated_at=time.time(),
        app_version="0.4.0",
    ))

    probe_called = False

    class FakeGemini:
        def list_models(self, probe: bool = True):
            nonlocal probe_called
            if probe:
                probe_called = True
            return [{"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"}]

    monkeypatch.setattr(
        models_module,
        "get_llm_provider",
        lambda name: FakeGemini() if name == "gemini" else (_ for _ in ()).throw(RuntimeError("N/A")),
    )

    res = client.get("/models?refresh=true")
    assert res.status_code == 200
    assert probe_called is True


def test_unconfigured_providers_are_never_attempted_or_probed(client, monkeypatch):
    """Verifies that providers without configured environment variables are skipped completely."""
    attempted_providers = []

    class FakeGemini:
        def list_models(self, probe: bool = True):
            return [{"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"}]

    def fake_get_provider(name: str):
        attempted_providers.append(name)
        if name == "gemini":
            return FakeGemini()
        raise AssertionError(f"Provider {name} should not have been attempted!")

    monkeypatch.setattr(models_module, "is_provider_configured", lambda name: name == "gemini")
    monkeypatch.setattr(models_module, "get_llm_provider", fake_get_provider)

    res = client.get("/models")
    assert res.status_code == 200
    data = res.json()

    assert len(data) == 1
    assert data[0]["id"] == "gemini"
    assert "openai" not in attempted_providers
    assert "anthropic" not in attempted_providers
