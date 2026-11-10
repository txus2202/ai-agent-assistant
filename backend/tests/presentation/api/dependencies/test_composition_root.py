from unittest.mock import AsyncMock, MagicMock
import pytest
from starlette.requests import HTTPConnection

from src.infrastructure.persistence.postgres_user_repository import PostgreSQLUserRepository
from src.infrastructure.persistence.sqlite_user_repository import SQLiteUserRepository
from src.presentation.api.config import Settings
from src.presentation.api.dependencies.auth import get_auth_service, reset_auth_service


def test_composition_root_sqlite_default(monkeypatch, tmp_path):
    reset_auth_service()
    settings = Settings(
        db_path=str(tmp_path / "sqlite.db"),
        auth_secret_key="test_secret_key_32_bytes_minimum_length",
        database_url="",
    )
    monkeypatch.setattr("src.presentation.api.dependencies.auth.get_settings", lambda: settings)

    mock_conn = MagicMock(spec=HTTPConnection)
    mock_conn.app.state = MagicMock()
    mock_conn.app.state.auth_service = None
    mock_conn.app.state.db_pool = None

    service = get_auth_service(mock_conn)
    assert isinstance(service._user_repo, SQLiteUserRepository)


def test_composition_root_postgres_wired(monkeypatch):
    reset_auth_service()
    settings = Settings(
        auth_secret_key="test_secret_key_32_bytes_minimum_length",
        database_url="postgresql://user:pass@localhost:5432/atenea",
    )
    monkeypatch.setattr("src.presentation.api.dependencies.auth.get_settings", lambda: settings)

    mock_conn = MagicMock(spec=HTTPConnection)
    mock_conn.app.state = MagicMock()
    mock_conn.app.state.auth_service = None
    mock_conn.app.state.db_pool = MagicMock()

    service = get_auth_service(mock_conn)
    assert isinstance(service._user_repo, PostgreSQLUserRepository)


def test_composition_root_postgres_missing_pool_raises_fail_fast(monkeypatch):
    reset_auth_service()
    settings = Settings(
        auth_secret_key="test_secret_key_32_bytes_minimum_length",
        database_url="postgresql://user:pass@localhost:5432/atenea",
    )
    monkeypatch.setattr("src.presentation.api.dependencies.auth.get_settings", lambda: settings)

    mock_conn = MagicMock(spec=HTTPConnection)
    mock_conn.app.state = MagicMock()
    mock_conn.app.state.auth_service = None
    mock_conn.app.state.db_pool = None

    with pytest.raises(RuntimeError) as exc:
        get_auth_service(mock_conn)
    assert "DATABASE_URL is configured for PostgreSQL, but no database pool" in str(exc.value)

