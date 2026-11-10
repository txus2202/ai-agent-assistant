"""
Infrastructure Adapter: SqliteAgentRepository

Persistent SQLite implementation of IAgentRepository (ADR-011).
Uses Python stdlib ``sqlite3`` — zero external dependencies.

Schema:
    agents(id TEXT PK, name TEXT, role TEXT, provider TEXT,
           model_name TEXT, status TEXT)

Connection strategy: one connection per operation via context manager,
which guarantees auto-commit on success and rollback on exception.
"""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from typing import Generator

from src.domain.entities.agent import Agent, AgentStatus
from src.domain.exceptions import RepositoryError
from src.domain.ports.agent_repository import IAgentRepository

_CREATE_AGENTS_TABLE = """
    CREATE TABLE IF NOT EXISTS agents (
        id          TEXT PRIMARY KEY,
        name        TEXT NOT NULL,
        role        TEXT NOT NULL,
        provider    TEXT NOT NULL,
        model_name  TEXT NOT NULL,
        status      TEXT NOT NULL DEFAULT 'idle'
    )
"""

_UPSERT_AGENT = """
    INSERT INTO agents (id, name, role, provider, model_name, status)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
        name       = excluded.name,
        role       = excluded.role,
        provider   = excluded.provider,
        model_name = excluded.model_name,
        status     = excluded.status
"""


class SqliteAgentRepository(IAgentRepository):
    """
    SQLite-backed implementation of ``IAgentRepository``.

    Args:
        db_path: Absolute or relative path to the ``.db`` file.
                 The file and its parent directory must be writable.
    """

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._init_schema()

    # ------------------------------------------------------------------
    # IAgentRepository implementation
    # ------------------------------------------------------------------

    def save(self, agent: Agent) -> None:
        try:
            with self._connection() as conn:
                conn.execute(
                    _UPSERT_AGENT,
                    (
                        str(agent.id),
                        agent.name,
                        agent.role,
                        agent.provider,
                        agent.model_name,
                        agent.status.value,
                    ),
                )
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to save agent {agent.id}: {exc}") from exc

    def find_by_id(self, agent_id: uuid.UUID) -> Agent | None:
        try:
            with self._connection() as conn:
                row = conn.execute(
                    "SELECT * FROM agents WHERE id = ?", (str(agent_id),)
                ).fetchone()
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to query agent {agent_id}: {exc}") from exc

        return self._row_to_agent(row) if row else None

    def find_all(self) -> list[Agent]:
        try:
            with self._connection() as conn:
                rows = conn.execute("SELECT * FROM agents").fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to fetch all agents: {exc}") from exc

        return [self._row_to_agent(row) for row in rows]

    def delete(self, agent_id: uuid.UUID) -> None:
        try:
            with self._connection() as conn:
                conn.execute("DELETE FROM agents WHERE id = ?", (str(agent_id),))
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to delete agent {agent_id}: {exc}") from exc

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        try:
            with self._connection() as conn:
                conn.execute(_CREATE_AGENTS_TABLE)
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to initialise schema: {exc}") from exc

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _row_to_agent(row: sqlite3.Row) -> Agent:
        """Reconstitute an Agent entity from a database row."""
        data = dict(row)
        return Agent(
            agent_id=uuid.UUID(data["id"]),
            name=data["name"],
            role=data["role"],
            provider=data["provider"],
            model_name=data["model_name"],
            status=AgentStatus(data["status"]),
        )
