"""
Shared SQLite connection management for infrastructure persistence adapters.

Provides ``SqliteConnectionManager`` enforcing WAL journal mode, busy timeout,
synchronous=NORMAL, foreign keys, commit/rollback handling, and guaranteed
connection closure in ``finally``.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager


class SqliteConnectionManager:
    """Reusable base/helper managing SQLite connection lifecycle and PRAGMAs."""

    _sqlite_timeout: float = 15.0

    def __init__(self, db_path: str, timeout: float = 15.0) -> None:
        self._db_path = str(db_path)
        self._sqlite_timeout = timeout

    @contextmanager
    def connection(self, *, timeout: float | None = None) -> Generator[sqlite3.Connection, None, None]:
        resolved_timeout = self._sqlite_timeout if timeout is None else timeout
        db_path = str(self._db_path)
        conn = sqlite3.connect(db_path, timeout=resolved_timeout)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA busy_timeout=10000")
            if db_path != ":memory:" and not db_path.startswith("file::memory:"):
                conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        with self.connection() as conn:
            yield conn

