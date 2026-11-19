from datetime import datetime
from typing import Any, Optional
from src.domain.entities.user import User
from src.domain.exceptions import RepositoryError, UserAlreadyExistsError
from src.domain.ports.user_repository import IUserRepository

_CREATE_PG_USERS_TABLE = """
    CREATE TABLE IF NOT EXISTS users (
        id            VARCHAR(64) PRIMARY KEY,
        username      VARCHAR(100) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        is_admin      BOOLEAN NOT NULL DEFAULT FALSE,
        is_active     BOOLEAN NOT NULL DEFAULT TRUE,
        token_version INT NOT NULL DEFAULT 1,
        deleted_at    TIMESTAMPTZ,
        created_at    TIMESTAMPTZ NOT NULL
    );
    ALTER TABLE users ADD COLUMN IF NOT EXISTS token_version INT NOT NULL DEFAULT 1;
    ALTER TABLE users ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
    CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
"""


class PostgreSQLUserRepository(IUserRepository):
    """
    PostgreSQL adapter for IUserRepository.
    Designed for asyncpg / psycopg connection pools.
    """

    def __init__(self, pool: Any) -> None:
        self._pool = pool

    async def init_schema(self) -> None:
        """Create the users table and indexes if they do not exist."""
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(_CREATE_PG_USERS_TABLE)
        except Exception as exc:
            raise RepositoryError(f"Failed to initialize PostgreSQL users schema: {exc}") from exc

    def _record_to_user(self, record: dict[str, Any]) -> User:
        created_at = record["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        deleted_at = record.get("deleted_at")
        if isinstance(deleted_at, str):
            deleted_at = datetime.fromisoformat(deleted_at)
        return User(
            id=record["id"],
            username=record["username"],
            password_hash=record["password_hash"],
            is_admin=bool(record["is_admin"]),
            is_active=bool(record["is_active"]),
            token_version=int(record.get("token_version", 1)),
            deleted_at=deleted_at,
            created_at=created_at,
        )

    async def get_by_id(self, user_id: str) -> Optional[User]:
        query = "SELECT id, username, password_hash, is_admin, is_active, token_version, deleted_at, created_at FROM users WHERE id = $1"
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, user_id)
                return self._record_to_user(dict(row)) if row else None
        except Exception as exc:
            raise RepositoryError(f"Failed to fetch user by id '{user_id}': {exc}") from exc

    async def get_by_username(self, username: str) -> Optional[User]:
        normalized = username.strip().lower()
        query = "SELECT id, username, password_hash, is_admin, is_active, token_version, deleted_at, created_at FROM users WHERE username = $1"
        try:
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(query, normalized)
                return self._record_to_user(dict(row)) if row else None
        except Exception as exc:
            raise RepositoryError(f"Failed to fetch user by username '{normalized}': {exc}") from exc

    async def save(self, user: User) -> None:
        query = """
            INSERT INTO users (id, username, password_hash, is_admin, is_active, token_version, deleted_at, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (id) DO UPDATE SET
                username = EXCLUDED.username,
                password_hash = EXCLUDED.password_hash,
                is_admin = EXCLUDED.is_admin,
                is_active = EXCLUDED.is_active,
                token_version = EXCLUDED.token_version,
                deleted_at = EXCLUDED.deleted_at
        """
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    query,
                    user.id,
                    user.username,
                    user.password_hash,
                    user.is_admin,
                    user.is_active,
                    user.token_version,
                    user.deleted_at,
                    user.created_at,
                )
        except Exception as exc:
            if "unique" in str(exc).lower() and "username" in str(exc).lower():
                raise UserAlreadyExistsError(f"User with username '{user.username}' already exists") from exc
            raise RepositoryError(f"Failed to save user in PostgreSQL: {exc}") from exc

    async def count_users(self) -> int:
        query = "SELECT COUNT(*) FROM users"
        try:
            async with self._pool.acquire() as conn:
                count = await conn.fetchval(query)
                return int(count or 0)
        except Exception as exc:
            raise RepositoryError(f"Failed to count users in PostgreSQL: {exc}") from exc

    async def list_users(self) -> list[User]:
        query = "SELECT id, username, password_hash, is_admin, is_active, token_version, deleted_at, created_at FROM users ORDER BY created_at ASC"
        try:
            async with self._pool.acquire() as conn:
                rows = await conn.fetch(query)
                return [self._record_to_user(dict(row)) for row in rows]
        except Exception as exc:
            raise RepositoryError(f"Failed to list users in PostgreSQL: {exc}") from exc

    async def delete(self, user_id: str) -> None:
        try:
            async with self._pool.acquire() as conn:
                query = "DELETE FROM users WHERE id = $1"
                await conn.execute(query, user_id)
        except Exception as exc:
            raise RepositoryError(f"Failed to delete user '{user_id}' in PostgreSQL: {exc}") from exc
