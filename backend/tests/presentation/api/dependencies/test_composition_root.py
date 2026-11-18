from unittest.mock import MagicMock
import pytest
from starlette.requests import HTTPConnection

from src.domain.ports.agent_config_repository import IAgentConfigRepository
from src.domain.ports.debate_repository import IDebateRepository
from src.infrastructure.persistence.postgres_user_repository import PostgreSQLUserRepository
from src.infrastructure.persistence.sqlite_agent_config_repository import SqliteAgentConfigRepository
from src.infrastructure.persistence.sqlite_debate_repository import SqliteDebateRepository
from src.infrastructure.persistence.sqlite_model_cache_repository import SqliteModelCacheRepository
from src.infrastructure.persistence.sqlite_user_repository import SQLiteUserRepository
from src.presentation.api.app import create_app
from src.presentation.api.config import Settings
from src.presentation.api.dependencies.auth import (
    get_agent_config_repository,
    get_auth_service,
    get_debate_repository,
    reset_auth_service,
)
from src.presentation.api.dependencies.model_cache import get_model_cache_repository


def _make_sqlite_settings(tmp_path, database_url: str = "") -> Settings:
    return Settings(
        sqlite_db_path=tmp_path / "sqlite.db",
        auth_secret_key="test_secret_key_32_bytes_minimum_length",
        database_url=database_url,
    )


def test_composition_root_sqlite_default(monkeypatch, tmp_path):
    reset_auth_service()
    settings = _make_sqlite_settings(tmp_path)
    monkeypatch.setattr("src.presentation.api.dependencies.auth.get_settings", lambda: settings)

    mock_conn = MagicMock(spec=HTTPConnection)
    mock_conn.app.state = MagicMock()
    mock_conn.app.state.auth_service = None
    mock_conn.app.state.db_pool = None

    try:
        service = get_auth_service(mock_conn)
        assert isinstance(service._user_repo, SQLiteUserRepository)
        assert isinstance(service._debate_repo, SqliteDebateRepository)
        assert isinstance(service._agent_config_repo, SqliteAgentConfigRepository)
        assert (tmp_path / "sqlite.db").exists()
    finally:
        reset_auth_service()


def test_composition_root_repositories_bound_to_configured_sqlite_path(monkeypatch, tmp_path):
    settings = _make_sqlite_settings(tmp_path)
    expected_db = str(tmp_path / "sqlite.db")

    debate_repo = get_debate_repository(settings)
    agent_cfg_repo = get_agent_config_repository(settings)
    assert isinstance(debate_repo, IDebateRepository)
    assert isinstance(debate_repo, SqliteDebateRepository)
    assert debate_repo._db_path == expected_db

    assert isinstance(agent_cfg_repo, IAgentConfigRepository)
    assert isinstance(agent_cfg_repo, SqliteAgentConfigRepository)
    assert agent_cfg_repo._db_path == expected_db

    get_model_cache_repository.cache_clear()
    monkeypatch.setattr("src.presentation.api.dependencies.model_cache.get_settings", lambda: settings)
    try:
        model_cache_repo = get_model_cache_repository()
        assert isinstance(model_cache_repo, SqliteModelCacheRepository)
        assert model_cache_repo._db_path == expected_db
    finally:
        get_model_cache_repository.cache_clear()


def test_composition_root_postgres_wired(monkeypatch, tmp_path):
    reset_auth_service()
    settings = _make_sqlite_settings(
        tmp_path,
        database_url="postgresql://user:pass@localhost:5432/atenea",
    )
    monkeypatch.setattr("src.presentation.api.dependencies.auth.get_settings", lambda: settings)

    mock_conn = MagicMock(spec=HTTPConnection)
    mock_conn.app.state = MagicMock()
    mock_conn.app.state.auth_service = None
    mock_conn.app.state.db_pool = MagicMock()

    try:
        service = get_auth_service(mock_conn)
        assert isinstance(service._user_repo, PostgreSQLUserRepository)
        assert isinstance(service._debate_repo, SqliteDebateRepository)
        assert isinstance(service._agent_config_repo, SqliteAgentConfigRepository)
    finally:
        reset_auth_service()


def test_composition_root_postgres_missing_pool_raises_fail_fast(monkeypatch, tmp_path):
    reset_auth_service()
    settings = _make_sqlite_settings(
        tmp_path,
        database_url="postgresql://user:pass@localhost:5432/atenea",
    )
    monkeypatch.setattr("src.presentation.api.dependencies.auth.get_settings", lambda: settings)

    mock_conn = MagicMock(spec=HTTPConnection)
    mock_conn.app.state = MagicMock()
    mock_conn.app.state.auth_service = None
    mock_conn.app.state.db_pool = None

    try:
        with pytest.raises(RuntimeError) as exc:
            get_auth_service(mock_conn)
        assert "DATABASE_URL is configured for PostgreSQL, but no database pool" in str(exc.value)
    finally:
        reset_auth_service()


def test_composition_root_prefers_app_state_auth_service(tmp_path):
    settings = _make_sqlite_settings(tmp_path)
    custom_auth = MagicMock()
    app = create_app(settings=settings, auth_service=custom_auth)

    assert app.state.settings is settings
    assert app.state.auth_service is custom_auth

    mock_conn = MagicMock(spec=HTTPConnection)
    mock_conn.app = app
    assert get_auth_service(mock_conn) is custom_auth
