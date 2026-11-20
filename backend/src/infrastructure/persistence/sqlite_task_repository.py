"""
Infrastructure Adapter: SqliteTaskRepository

Persistent SQLite implementation of ITaskRepository (ADR-011).
Uses Python stdlib ``sqlite3`` — zero external dependencies.

Schema:
    tasks(id TEXT PK, prompt TEXT, agent_id TEXT, status TEXT,
          result TEXT, created_at TEXT, dependencies TEXT)

Serialisation contract:
    - UUID      → str(uuid)          / uuid.UUID(str)
    - datetime  → isoformat()        / datetime.fromisoformat()
    - list[UUID]→ json.dumps([str])  / [uuid.UUID(s) for s in json.loads()]
    - TaskStatus→ status.value (str) / TaskStatus(str)

Reconstitution note: when loading from DB, status, result, and created_at
are set directly on the Task instance (bypassing the state machine).
This is intentional — the state machine governs *transitions*, not loading
from a trusted persistence layer (DDD reconstitution pattern).
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime

from src.domain.entities.task import Task, TaskStatus
from src.domain.exceptions import RepositoryError
from src.domain.ports.task_repository import ITaskRepository
from src.infrastructure.persistence.sqlite_base import SqliteConnectionManager

_CREATE_TASKS_TABLE = """
    CREATE TABLE IF NOT EXISTS tasks (
        id           TEXT PRIMARY KEY,
        prompt       TEXT NOT NULL,
        agent_id     TEXT NOT NULL,
        status       TEXT NOT NULL DEFAULT 'pending',
        result       TEXT,
        created_at   TEXT NOT NULL,
        dependencies TEXT NOT NULL DEFAULT '[]'
    )
"""

_UPSERT_TASK = """
    INSERT INTO tasks (id, prompt, agent_id, status, result, created_at, dependencies)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(id) DO UPDATE SET
        prompt       = excluded.prompt,
        agent_id     = excluded.agent_id,
        status       = excluded.status,
        result       = excluded.result,
        created_at   = excluded.created_at,
        dependencies = excluded.dependencies
"""


class SqliteTaskRepository(ITaskRepository, SqliteConnectionManager):
    """
    SQLite-backed implementation of ``ITaskRepository``.

    Args:
        db_path: Path to the ``.db`` file. Created on first use if absent.
    """

    def __init__(self, db_path: str) -> None:
        SqliteConnectionManager.__init__(self, db_path)
        self._init_schema()

    # ------------------------------------------------------------------
    # ITaskRepository implementation
    # ------------------------------------------------------------------

    def save(self, task: Task) -> None:
        try:
            with self._connection() as conn:
                conn.execute(
                    _UPSERT_TASK,
                    (
                        str(task.id),
                        task.prompt,
                        str(task.agent_id),
                        task.status.value,
                        task.result,
                        task.created_at.isoformat(),
                        json.dumps([str(dep) for dep in task.dependencies]),
                    ),
                )
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to save task {task.id}: {exc}") from exc

    def find_by_id(self, task_id: uuid.UUID) -> Task | None:
        try:
            with self._connection() as conn:
                row = conn.execute(
                    "SELECT * FROM tasks WHERE id = ?", (str(task_id),)
                ).fetchone()
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to query task {task_id}: {exc}") from exc

        return self._row_to_task(row) if row else None

    def find_by_agent_id(self, agent_id: uuid.UUID) -> list[Task]:
        try:
            with self._connection() as conn:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE agent_id = ?", (str(agent_id),)
                ).fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to query tasks for agent {agent_id}: {exc}") from exc

        return [self._row_to_task(row) for row in rows]

    def find_all(self) -> list[Task]:
        try:
            with self._connection() as conn:
                rows = conn.execute("SELECT * FROM tasks").fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to fetch all tasks: {exc}") from exc

        return [self._row_to_task(row) for row in rows]

    def delete(self, task_id: uuid.UUID) -> None:
        try:
            with self._connection() as conn:
                conn.execute("DELETE FROM tasks WHERE id = ?", (str(task_id),))
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to delete task {task_id}: {exc}") from exc

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _init_schema(self) -> None:
        try:
            with self._connection() as conn:
                conn.execute(_CREATE_TASKS_TABLE)
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to initialise schema: {exc}") from exc

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> Task:
        """
        Reconstitute a Task from a DB row.
        Sets status, result, and created_at directly — bypasses state machine
        intentionally (DDD reconstitution pattern, not a domain transition).
        """
        data = dict(row)
        dependencies = [uuid.UUID(dep) for dep in json.loads(data["dependencies"])]

        task = Task(
            task_id=uuid.UUID(data["id"]),
            prompt=data["prompt"],
            agent_id=uuid.UUID(data["agent_id"]),
            dependencies=dependencies,
        )
        # Reconstitution: restore persisted state directly
        task.status = TaskStatus(data["status"])
        task.result = data["result"]  # may be None
        task.created_at = datetime.fromisoformat(data["created_at"])

        return task
