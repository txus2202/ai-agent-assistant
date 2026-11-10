import sqlite3
from contextlib import contextmanager
from typing import Generator, List, Optional

from src.domain.exceptions import RepositoryError
from src.domain.ports.agent_config_repository import IAgentConfigRepository
from src.domain.value_objects.agent_config import AgentConfig

_CREATE_AGENT_CONFIGS_TABLE = """
    CREATE TABLE IF NOT EXISTS agent_configs (
        role        TEXT NOT NULL,
        provider    TEXT NOT NULL,
        model_name  TEXT NOT NULL,
        user_id     TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (role, user_id)
    )
"""

_UPSERT_AGENT_CONFIG = """
    INSERT INTO agent_configs (role, provider, model_name, user_id)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(role, user_id) DO UPDATE SET
        provider   = excluded.provider,
        model_name = excluded.model_name
"""


class SqliteAgentConfigRepository(IAgentConfigRepository):
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._init_schema()

    def save(self, config: AgentConfig) -> None:
        user_id = config.user_id or ""
        try:
            with self._connection() as conn:
                conn.execute(
                    _UPSERT_AGENT_CONFIG,
                    (config.role, config.provider, config.model_name, user_id),
                )
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to save agent config {config.role}: {exc}") from exc

    def find_by_role(self, role: str, user_id: Optional[str] = None) -> Optional[AgentConfig]:
        candidates = self._candidate_roles(role)
        try:
            with self._connection() as conn:
                row = None
                if user_id:
                    row = self._query_by_candidates(conn, candidates, user_id=user_id)
                if not row:
                    row = self._query_by_candidates(conn, candidates, user_id=None)
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to query agent config {role}: {exc}") from exc

        return self._row_to_config(row) if row else None

    @staticmethod
    def _candidate_roles(role: str) -> List[str]:
        candidates = [role]
        try:
            from src.domain.agents.sub_agent_profiles import get_profile
            profile = get_profile(role)
            for alt in (profile.display_name, profile.id):
                if alt not in candidates:
                    candidates.append(alt)
        except Exception:
            pass
        return candidates

    @staticmethod
    def _query_by_candidates(
        conn: sqlite3.Connection,
        candidates: List[str],
        user_id: Optional[str],
    ) -> Optional[sqlite3.Row]:
        for candidate in candidates:
            if user_id:
                row = conn.execute(
                    "SELECT * FROM agent_configs WHERE role = ? AND user_id = ?",
                    (candidate, user_id),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT * FROM agent_configs WHERE role = ? AND (user_id = '' OR user_id IS NULL)",
                    (candidate,),
                ).fetchone()
            if row:
                return row
        return None

    def find_all(self, user_id: Optional[str] = None) -> List[AgentConfig]:
        try:
            with self._connection() as conn:
                # 1. Start with global defaults
                rows_default = conn.execute(
                    "SELECT * FROM agent_configs WHERE user_id = '' OR user_id IS NULL"
                ).fetchall()
                configs_by_role = {r["role"]: self._row_to_config(r) for r in rows_default}

                # 2. If user_id specified, merge user-specific overrides
                if user_id:
                    rows_user = conn.execute(
                        "SELECT * FROM agent_configs WHERE user_id = ?",
                        (user_id,),
                    ).fetchall()
                    for r in rows_user:
                        configs_by_role[r["role"]] = self._row_to_config(r)

                return list(configs_by_role.values())
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to fetch all agent configs: {exc}") from exc

    def delete_by_user_id(self, user_id: str) -> int:
        """Deletes all custom agent configurations for a specific user."""
        if not user_id:
            return 0
        try:
            with self._connection() as conn:
                cursor = conn.execute("DELETE FROM agent_configs WHERE user_id = ?", (user_id,))
                return cursor.rowcount
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to delete agent configs for user {user_id}: {exc}") from exc

    def _init_schema(self) -> None:
        try:
            with self._connection() as conn:
                # Check if table exists
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='agent_configs'"
                )
                if not cursor.fetchone():
                    conn.execute(_CREATE_AGENT_CONFIGS_TABLE)
                    return

                # Table exists: check primary key and columns
                cursor = conn.execute("PRAGMA table_info(agent_configs)")
                cols = cursor.fetchall()
                col_names = [c["name"] for c in cols]
                pk_cols = [c["name"] for c in cols if c["pk"] > 0]

                # Migrate if user_id is missing or PK is only (role)
                if "user_id" not in col_names or pk_cols == ["role"]:
                    conn.execute("""
                        CREATE TABLE IF NOT EXISTS agent_configs_v2 (
                            role        TEXT NOT NULL,
                            provider    TEXT NOT NULL,
                            model_name  TEXT NOT NULL,
                            user_id     TEXT NOT NULL DEFAULT '',
                            PRIMARY KEY (role, user_id)
                        )
                    """)
                    if "user_id" in col_names:
                        conn.execute("""
                            INSERT OR IGNORE INTO agent_configs_v2 (role, provider, model_name, user_id)
                            SELECT role, provider, model_name, COALESCE(user_id, '') FROM agent_configs
                        """)
                    else:
                        conn.execute("""
                            INSERT OR IGNORE INTO agent_configs_v2 (role, provider, model_name, user_id)
                            SELECT role, provider, model_name, '' FROM agent_configs
                        """)
                    conn.execute("DROP TABLE agent_configs")
                    conn.execute("ALTER TABLE agent_configs_v2 RENAME TO agent_configs")
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
        data = dict(row)
        uid = data.get("user_id")
        return AgentConfig(
            role=data["role"],
            provider=data["provider"],
            model_name=data["model_name"],
            user_id=uid if uid else None,
        )


class UserScopedAgentConfigRepository(IAgentConfigRepository):
    """
    Decorator around IAgentConfigRepository that automatically scopes queries
    and saves to a specific user_id, falling back to system defaults.
    """

    def __init__(self, inner: IAgentConfigRepository, user_id: Optional[str]) -> None:
        self._inner = inner
        self._user_id = user_id

    def save(self, config: AgentConfig) -> None:
        scoped = AgentConfig(
            role=config.role,
            provider=config.provider,
            model_name=config.model_name,
            user_id=config.user_id or self._user_id,
        )
        self._inner.save(scoped)

    def find_by_role(self, role: str, user_id: Optional[str] = None) -> Optional[AgentConfig]:
        target = user_id if user_id is not None else self._user_id
        return self._inner.find_by_role(role, user_id=target)

    def find_all(self, user_id: Optional[str] = None) -> List[AgentConfig]:
        target = user_id if user_id is not None else self._user_id
        return self._inner.find_all(user_id=target)

    def delete_by_user_id(self, user_id: str) -> int:
        target = user_id or self._user_id or ""
        return self._inner.delete_by_user_id(target)

