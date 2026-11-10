from datetime import datetime, timezone
import sqlite3
from typing import Optional
from src.domain.entities.user import User
from src.domain.exceptions import RepositoryError, UserAlreadyExistsError
from src.domain.ports.user_repository_port import IUserRepository

_CREATE_USERS_TABLE = """
    CREATE TABLE IF NOT EXISTS users (
        id            TEXT PRIMARY KEY,
        username      TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        is_admin      INTEGER NOT NULL DEFAULT 0,
        is_active     INTEGER NOT NULL DEFAULT 1,
        token_version INTEGER NOT NULL DEFAULT 1,
        deleted_at    TEXT,
        created_at    TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
"""


class SQLiteUserRepository(IUserRepository):
    """
    SQLite adapter for IUserRepository.
    Uses Python standard library sqlite3.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._init_schema()

    def _init_schema(self) -> None:
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.executescript(_CREATE_USERS_TABLE)
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(users)")
                columns = [row[1] for row in cursor.fetchall()]
                if "token_version" not in columns:
                    cursor.execute("ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 1")
                if "deleted_at" not in columns:
                    cursor.execute("ALTER TABLE users ADD COLUMN deleted_at TEXT")
                conn.commit()
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to initialize users schema: {exc}") from exc

    def _row_to_user(self, row: tuple) -> User:
        if len(row) == 8:
            user_id, username, password_hash, is_admin, is_active, token_version, deleted_at_str, created_at_str = row
            deleted_at = datetime.fromisoformat(deleted_at_str) if deleted_at_str else None
        else:
            user_id, username, password_hash, is_admin, is_active, created_at_str = row
            token_version = 1
            deleted_at = None

        created_at = datetime.fromisoformat(created_at_str)
        return User(
            id=user_id,
            username=username,
            password_hash=password_hash,
            is_admin=bool(is_admin),
            is_active=bool(is_active),
            token_version=token_version,
            deleted_at=deleted_at,
            created_at=created_at,
        )

    async def get_by_id(self, user_id: str) -> Optional[User]:
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, username, password_hash, is_admin, is_active, token_version, deleted_at, created_at FROM users WHERE id = ?",
                    (user_id,),
                )
                row = cursor.fetchone()
                return self._row_to_user(row) if row else None
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to fetch user by id '{user_id}': {exc}") from exc

    async def get_by_username(self, username: str) -> Optional[User]:
        normalized = username.strip().lower()
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, username, password_hash, is_admin, is_active, token_version, deleted_at, created_at FROM users WHERE username = ?",
                    (normalized,),
                )
                row = cursor.fetchone()
                return self._row_to_user(row) if row else None
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to fetch user by username '{normalized}': {exc}") from exc

    async def save(self, user: User) -> None:
        try:
            with sqlite3.connect(self._db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO users (id, username, password_hash, is_admin, is_active, token_version, deleted_at, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        username = excluded.username,
                        password_hash = excluded.password_hash,
                        is_admin = excluded.is_admin,
                        is_active = excluded.is_active,
                        token_version = excluded.token_version,
                        deleted_at = excluded.deleted_at
                    """,
                    (
                        user.id,
                        user.username,
                        user.password_hash,
                        1 if user.is_admin else 0,
                        1 if user.is_active else 0,
                        user.token_version,
                        user.deleted_at.isoformat() if user.deleted_at else None,
                        user.created_at.isoformat(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            if "UNIQUE constraint failed: users.username" in str(exc) or "UNIQUE" in str(exc):
                raise UserAlreadyExistsError(f"User with username '{user.username}' already exists") from exc
            raise RepositoryError(f"Integrity error saving user: {exc}") from exc
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to save user: {exc}") from exc

    async def count_users(self) -> int:
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM users")
                row = cursor.fetchone()
                return row[0] if row else 0
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to count users: {exc}") from exc

    async def list_users(self) -> list[User]:
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, username, password_hash, is_admin, is_active, token_version, deleted_at, created_at FROM users ORDER BY created_at ASC"
                )
                rows = cursor.fetchall()
                return [self._row_to_user(row) for row in rows]
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to list users: {exc}") from exc

    async def delete(self, user_id: str) -> None:
        try:
            with sqlite3.connect(self._db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
                conn.commit()
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to delete user '{user_id}': {exc}") from exc
