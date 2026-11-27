"""
Infrastructure Adapter: SqliteUserTopologyRepository

Persists per-operator debate topology preferences in SQLite (`user_topologies` table)
with automatic schema creation and cascade-compatible `delete_by_user_id`.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Any

from src.domain.exceptions import RepositoryError
from src.domain.ports.user_topology_repository import IUserTopologyRepository
from src.domain.value_objects.user_topology_config import UserTopologyConfig
from src.infrastructure.persistence.sqlite_base import SqliteConnectionManager

_CREATE_USER_TOPOLOGIES_TABLE = """
    CREATE TABLE IF NOT EXISTS user_topologies (
        user_id       TEXT PRIMARY KEY,
        interpreters  TEXT NOT NULL DEFAULT '[]',
        proposers     TEXT NOT NULL DEFAULT '[]',
        reviewers     TEXT NOT NULL DEFAULT '[]',
        evaluators    TEXT NOT NULL DEFAULT '[]',
        implementers  TEXT NOT NULL DEFAULT '[]',
        review_rounds INTEGER NOT NULL DEFAULT 1,
        updated_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
"""

_UPSERT_USER_TOPOLOGY = """
    INSERT INTO user_topologies (
        user_id, interpreters, proposers, reviewers, evaluators, implementers, review_rounds, updated_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
    ON CONFLICT(user_id) DO UPDATE SET
        interpreters  = excluded.interpreters,
        proposers     = excluded.proposers,
        reviewers     = excluded.reviewers,
        evaluators    = excluded.evaluators,
        implementers  = excluded.implementers,
        review_rounds = excluded.review_rounds,
        updated_at    = CURRENT_TIMESTAMP
"""


def _parse_json_tuple(raw: Any) -> tuple[str, ...]:
    if not raw:
        return ()
    try:
        parsed = json.loads(str(raw))
    except (ValueError, TypeError):
        return ()
    if isinstance(parsed, list):
        return tuple(str(item) for item in parsed if item)
    return ()


class SqliteUserTopologyRepository(IUserTopologyRepository, SqliteConnectionManager):
    """SQLite-backed implementation of ``IUserTopologyRepository``."""

    def __init__(self, db_path: str) -> None:
        SqliteConnectionManager.__init__(self, db_path)
        self._init_schema()

    def _init_schema(self) -> None:
        try:
            with self._connection() as conn:
                conn.execute(_CREATE_USER_TOPOLOGIES_TABLE)
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to initialize user_topologies schema: {exc}") from exc

    def find_by_user_id(self, user_id: str) -> UserTopologyConfig | None:
        if not user_id:
            return None
        try:
            with self._connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT user_id, interpreters, proposers, reviewers, evaluators, implementers, review_rounds
                    FROM user_topologies
                    WHERE user_id = ?
                    """,
                    (user_id,),
                )
                row = cursor.fetchone()
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to query user topology for {user_id}: {exc}") from exc

        if row is None:
            return None

        return UserTopologyConfig(
            user_id=str(row[0]),
            interpreters=_parse_json_tuple(row[1]),
            proposers=_parse_json_tuple(row[2]),
            reviewers=_parse_json_tuple(row[3]),
            evaluators=_parse_json_tuple(row[4]),
            implementers=_parse_json_tuple(row[5]),
            review_rounds=int(row[6]) if row[6] is not None else 1,
        )

    def save(self, config: UserTopologyConfig) -> None:
        try:
            with self._connection() as conn:
                conn.execute(
                    _UPSERT_USER_TOPOLOGY,
                    (
                        config.user_id,
                        json.dumps(list(config.interpreters)),
                        json.dumps(list(config.proposers)),
                        json.dumps(list(config.reviewers)),
                        json.dumps(list(config.evaluators)),
                        json.dumps(list(config.implementers)),
                        int(config.review_rounds),
                    ),
                )
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to save user topology for {config.user_id}: {exc}") from exc

    def delete_by_user_id(self, user_id: str) -> None:
        if not user_id:
            return
        try:
            with self._connection() as conn:
                conn.execute("DELETE FROM user_topologies WHERE user_id = ?", (user_id,))
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to delete user topology for {user_id}: {exc}") from exc

