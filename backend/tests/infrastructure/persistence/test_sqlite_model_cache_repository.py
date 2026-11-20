import pytest
import time
from src.domain.ports.model_cache_repository import CachedModelCatalog
from src.infrastructure.persistence.sqlite_model_cache_repository import SqliteModelCacheRepository

@pytest.fixture
def repo(tmp_path):
    db_path = str(tmp_path / "test_model_cache.db")
    return SqliteModelCacheRepository(db_path, app_version="0.4.0")

def test_save_and_get(repo):
    catalog = CachedModelCatalog(
        provider="gemini",
        models=[{"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"}],
        is_verified=True,
        updated_at=time.time(),
        app_version="0.4.0",
    )
    repo.save(catalog)

    retrieved = repo.get("gemini")
    assert retrieved is not None
    assert retrieved.provider == "gemini"
    assert retrieved.models == [{"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"}]
    assert retrieved.is_verified is True
    assert retrieved.app_version == "0.4.0"

def test_get_returns_none_on_version_mismatch(tmp_path):
    db_path = str(tmp_path / "test_mismatch.db")
    repo_v1 = SqliteModelCacheRepository(db_path, app_version="0.4.0")
    repo_v1.save(CachedModelCatalog(
        provider="gemini",
        models=[{"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"}],
        is_verified=True,
        updated_at=time.time(),
        app_version="0.4.0",
    ))

    # New deployment with version 0.5.0 reads same DB
    repo_v2 = SqliteModelCacheRepository(db_path, app_version="0.5.0")
    retrieved = repo_v2.get("gemini")
    assert retrieved is None  # Invalidated automatically on version mismatch!

def test_acquire_and_release_probe_lock(repo, tmp_path):
    # Pod 1 acquires lock
    assert repo.acquire_probe_lock("openai", timeout_seconds=30.0) is True

    # Pod 2 (separate connection to same DB) tries to acquire lock
    repo_pod2 = SqliteModelCacheRepository(repo._db_path, app_version="0.4.0")
    assert repo_pod2.acquire_probe_lock("openai", timeout_seconds=30.0) is False

    # Pod 1 releases lock
    repo.release_probe_lock("openai")

    # Pod 2 can now acquire lock
    assert repo_pod2.acquire_probe_lock("openai", timeout_seconds=30.0) is True

def test_expired_probe_lock_can_be_reacquired(repo):
    # Simulate a crashed pod that held a lock that expired
    assert repo.acquire_probe_lock("gemini", timeout_seconds=-5.0) is True

    # Second pod attempts to acquire: should reclaim expired lock
    assert repo.acquire_probe_lock("gemini", timeout_seconds=30.0) is True

def test_invalidate_all(repo):
    repo.save(CachedModelCatalog(
        provider="gemini",
        models=[{"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"}],
        is_verified=True,
        updated_at=time.time(),
        app_version="0.4.0",
    ))
    repo.save(CachedModelCatalog(
        provider="openai",
        models=[{"id": "gpt-4o", "name": "GPT-4O"}],
        is_verified=True,
        updated_at=time.time(),
        app_version="0.4.0",
    ))

    assert repo.get("gemini") is not None
    assert repo.get("openai") is not None

    repo.invalidate_all()

    assert repo.get("gemini") is None
    assert repo.get("openai") is None

