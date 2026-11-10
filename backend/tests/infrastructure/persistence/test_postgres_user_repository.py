from unittest.mock import AsyncMock, MagicMock
import pytest
from src.domain.entities.user import User
from src.domain.exceptions import UserAlreadyExistsError
from src.infrastructure.persistence.postgres_user_repository import PostgreSQLUserRepository


@pytest.fixture
def mock_pool():
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__.return_value = conn
    return pool, conn


@pytest.mark.asyncio
async def test_postgres_user_repo_count(mock_pool):
    pool, conn = mock_pool
    conn.fetchval.return_value = 3

    repo = PostgreSQLUserRepository(pool=pool)
    count = await repo.count_users()

    assert count == 3
    conn.fetchval.assert_awaited_once_with("SELECT COUNT(*) FROM users")


@pytest.mark.asyncio
async def test_postgres_user_repo_get_by_username(mock_pool):
    pool, conn = mock_pool
    conn.fetchrow.return_value = {
        "id": "u-pg-1",
        "username": "pguser",
        "password_hash": "$argon2id$pghash",
        "is_admin": True,
        "is_active": True,
        "created_at": "2026-11-09T10:00:00+00:00",
    }

    repo = PostgreSQLUserRepository(pool=pool)
    user = await repo.get_by_username("PGUser")

    assert user is not None
    assert user.id == "u-pg-1"
    assert user.username == "pguser"
    assert user.is_admin is True
    conn.fetchrow.assert_awaited_once_with(
        "SELECT id, username, password_hash, is_admin, is_active, token_version, deleted_at, created_at FROM users WHERE username = $1",
        "pguser",
    )


@pytest.mark.asyncio
async def test_postgres_user_repo_init_schema(mock_pool):
    pool, conn = mock_pool
    repo = PostgreSQLUserRepository(pool=pool)
    await repo.init_schema()

    conn.execute.assert_awaited_once()
    sql_executed = conn.execute.call_args[0][0]
    assert "CREATE TABLE IF NOT EXISTS users" in sql_executed


@pytest.mark.asyncio
async def test_postgres_user_repo_delete(mock_pool):
    pool, conn = mock_pool
    repo = PostgreSQLUserRepository(pool=pool)
    await repo.delete("u-pg-del-123")

    conn.execute.assert_awaited_once_with("DELETE FROM users WHERE id = $1", "u-pg-del-123")


@pytest.mark.asyncio
async def test_postgres_user_repo_get_by_id(mock_pool):
    pool, conn = mock_pool
    conn.fetchrow.return_value = {
        "id": "u-pg-2",
        "username": "pguser2",
        "password_hash": "$argon2id$pghash2",
        "is_admin": False,
        "is_active": True,
        "created_at": "2026-11-09T10:00:00+00:00",
    }
    repo = PostgreSQLUserRepository(pool=pool)
    user = await repo.get_by_id("u-pg-2")

    assert user is not None
    assert user.id == "u-pg-2"
    assert user.username == "pguser2"
    assert user.is_admin is False
    conn.fetchrow.assert_awaited_once_with(
        "SELECT id, username, password_hash, is_admin, is_active, token_version, deleted_at, created_at FROM users WHERE id = $1",
        "u-pg-2",
    )


@pytest.mark.asyncio
async def test_postgres_user_repo_list_users(mock_pool):
    pool, conn = mock_pool
    conn.fetch.return_value = [
        {
            "id": "u-pg-1",
            "username": "pguser1",
            "password_hash": "$hash1",
            "is_admin": True,
            "is_active": True,
            "created_at": "2026-11-09T10:00:00+00:00",
        },
        {
            "id": "u-pg-2",
            "username": "pguser2",
            "password_hash": "$hash2",
            "is_admin": False,
            "is_active": False,
            "created_at": "2026-11-09T11:00:00+00:00",
        },
    ]
    repo = PostgreSQLUserRepository(pool=pool)
    users = await repo.list_users()

    assert len(users) == 2
    assert users[0].username == "pguser1"
    assert users[1].username == "pguser2"
    assert users[1].is_active is False


@pytest.mark.asyncio
async def test_postgres_user_repo_save_duplicate_raises(mock_pool):
    from datetime import datetime, timezone
    pool, conn = mock_pool
    conn.execute.side_effect = Exception("duplicate key value violates unique constraint 'users_username_key'")

    repo = PostgreSQLUserRepository(pool=pool)
    user = User(
        id="u-pg-dup",
        username="existing",
        password_hash="hash",
        is_admin=False,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )

    with pytest.raises(UserAlreadyExistsError):
        await repo.save(user)


