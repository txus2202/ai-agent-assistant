import sqlite3
from contextlib import contextmanager
from typing import Generator, List, Optional

from src.domain.exceptions import RepositoryError
from src.domain.ports.agent_config_repository import IAgentConfigRepository
from src.domain.value_objects.agent_config import AgentConfig

_CREATE_AGENT_CONFIGS_TABLE = """
    CREATE TABLE IF NOT EXISTS agent_configs (
        role        TEXT PRIMARY KEY,
        provider    TEXT NOT NULL,
        model_name  TEXT NOT NULL
    )
"""

_UPSERT_AGENT_CONFIG = """
    INSERT INTO agent_configs (role, provider, model_name)
    VALUES (?, ?, ?)
    ON CONFLICT(role) DO UPDATE SET
        provider   = excluded.provider,
        model_name = excluded.model_name
"""

class SqliteAgentConfigRepository(IAgentConfigRepository):
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._init_schema()

    def save(self, config: AgentConfig) -> None:
        try:
            with self._connection() as conn:
                conn.execute(
                    _UPSERT_AGENT_CONFIG,
                    (config.role, config.provider, config.model_name),
                )
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to save agent config {config.role}: {exc}") from exc

    def find_by_role(self, role: str) -> Optional[AgentConfig]:
        try:
            with self._connection() as conn:
                row = conn.execute(
                    "SELECT * FROM agent_configs WHERE role = ?", (role,)
                ).fetchone()
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to query agent config {role}: {exc}") from exc

        return self._row_to_config(row) if row else None

    def find_all(self) -> List[AgentConfig]:
        try:
            with self._connection() as conn:
                rows = conn.execute("SELECT * FROM agent_configs").fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to fetch all agent configs: {exc}") from exc

        return [self._row_to_config(row) for row in rows]

    def _init_schema(self) -> None:
        try:
            with self._connection() as conn:
                conn.execute(_CREATE_AGENT_CONFIGS_TABLE)
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
    def _row_to_config(row: sqlite3.Row) -> AgentConfig:
        return AgentConfig(
            role=row["role"],
            provider=row["provider"],
            model_name=row["model_name"],
        )
