"""
Infrastructure Adapter: SqliteModelCacheRepository

Implements IModelCacheRepository using SQLite.
Stores verified and unverified model catalogs in `model_cache` table and supports
atomic distributed locking to prevent duplicate probes across cluster replicas.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from typing import Generator, Optional

from src.domain.exceptions import RepositoryError
from src.domain.ports.model_cache_port import CachedModelCatalog, IModelCacheRepository

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS model_cache (
    provider TEXT PRIMARY KEY,
    models_json TEXT NOT NULL,
    is_verified INTEGER NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL,
    app_version TEXT NOT NULL,
    is_probing INTEGER NOT NULL DEFAULT 0,
    probe_lock_until REAL NOT NULL DEFAULT 0.0
);
"""


class SqliteModelCacheRepository(IModelCacheRepository):
    def __init__(self, db_path: str, app_version: str = "0.4.0") -> None:
        self._db_path = db_path
        self._app_version = app_version
        self._init_schema()

    def _init_schema(self) -> None:
        try:
            with self._connection() as conn:
                conn.execute(_CREATE_TABLE_SQL)
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to initialise model_cache schema: {exc}") from exc

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self._db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get(self, provider: str) -> Optional[CachedModelCatalog]:
        try:
            with self._connection() as conn:
                cursor = conn.execute(
                    "SELECT provider, models_json, is_verified, updated_at, app_version FROM model_cache WHERE provider = ?",
                    (provider,),
                )
                row = cursor.fetchone()
                if not row:
                    return None

                # Invalidate if deployment app_version changed
                if row["app_version"] != self._app_version:
                    return None

                models = json.loads(row["models_json"])
                return CachedModelCatalog(
                    provider=row["provider"],
                    models=models,
                    is_verified=bool(row["is_verified"]),
                    updated_at=float(row["updated_at"]),
                    app_version=row["app_version"],
                )
        except (sqlite3.Error, json.JSONDecodeError) as exc:
            raise RepositoryError(f"Failed to fetch model cache for {provider}: {exc}") from exc

    def save(self, catalog: CachedModelCatalog) -> None:
        try:
            models_json = json.dumps(catalog.models)
            with self._connection() as conn:
                conn.execute(
                    """
                    INSERT INTO model_cache (provider, models_json, is_verified, updated_at, app_version, is_probing, probe_lock_until)
                    VALUES (?, ?, ?, ?, ?, 0, 0.0)
                    ON CONFLICT(provider) DO UPDATE SET
                        models_json = excluded.models_json,
                        is_verified = excluded.is_verified,
                        updated_at = excluded.updated_at,
                        app_version = excluded.app_version,
                        is_probing = 0,
                        probe_lock_until = 0.0
                    """,
                    (
                        catalog.provider,
                        models_json,
                        1 if catalog.is_verified else 0,
                        catalog.updated_at,
                        catalog.app_version,
                    ),
                )
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to save model cache for {catalog.provider}: {exc}") from exc

    def acquire_probe_lock(self, provider: str, timeout_seconds: float = 60.0) -> bool:
        now = time.time()
        lock_until = now + timeout_seconds
        try:
            with self._connection() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO model_cache (provider, models_json, is_verified, updated_at, app_version, is_probing, probe_lock_until)
                    VALUES (?, '[]', 0, ?, ?, 1, ?)
                    ON CONFLICT(provider) DO UPDATE SET
                        is_probing = 1,
                        probe_lock_until = excluded.probe_lock_until
                    WHERE is_probing = 0 OR probe_lock_until < ?
                    """,
                    (provider, now, self._app_version, lock_until, now),
                )
                return cursor.rowcount > 0
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to acquire probe lock for {provider}: {exc}") from exc

    def release_probe_lock(self, provider: str) -> None:
        try:
            with self._connection() as conn:
                conn.execute(
                    "UPDATE model_cache SET is_probing = 0, probe_lock_until = 0.0 WHERE provider = ?",
                    (provider,),
                )
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to release probe lock for {provider}: {exc}") from exc

    def invalidate_all(self) -> None:
        try:
            with self._connection() as conn:
                conn.execute("DELETE FROM model_cache")
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to invalidate model cache: {exc}") from exc

