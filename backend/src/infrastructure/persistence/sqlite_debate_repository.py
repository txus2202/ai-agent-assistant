import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Generator, List, Optional

from src.domain.exceptions import RepositoryError
from src.domain.ports.debate_repository import IDebateRepository
from src.domain.value_objects.debate_record import DebateRecord

_CREATE_DEBATES_TABLE = """
    CREATE TABLE IF NOT EXISTS debates (
        id            TEXT PRIMARY KEY,
        created_at    TEXT NOT NULL,
        user_request  TEXT NOT NULL,
        target_agent  TEXT NOT NULL,
        events_json   TEXT NOT NULL,
        status        TEXT NOT NULL,
        user_id       TEXT
    )
"""

class SqliteDebateRepository(IDebateRepository):
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._init_schema()

    def create(self, debate: DebateRecord) -> None:
        try:
            with self._connection() as conn:
                conn.execute(
                    "INSERT INTO debates (id, created_at, user_request, target_agent, events_json, status, user_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        debate.id,
                        debate.created_at.isoformat(),
                        debate.user_request,
                        debate.target_agent,
                        debate.events_json,
                        debate.status,
                        debate.user_id,
                    ),
                )
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to create debate {debate.id}: {exc}") from exc

    def append_event(self, debate_id: str, event_json: str) -> None:
        # SQLite doesn't have a great array append in JSON string form without JSON1 extension overhead.
        # We can read the current events_json, append the object, and write it back.
        # However, a simpler string manipulation can work: 
        # If it's "[]", replace with "[{event}]"
        # If it's "[{...}]", strip last ']' and append ", {event}]"
        # But for robustness we'll just parse and dump, as the event stream is relatively small.
        try:
            with self._connection() as conn:
                row = conn.execute("SELECT events_json FROM debates WHERE id = ?", (debate_id,)).fetchone()
                if row:
                    events = json.loads(row["events_json"])
                    events.append(json.loads(event_json))
                    new_events_str = json.dumps(events)
                    conn.execute("UPDATE debates SET events_json = ? WHERE id = ?", (new_events_str, debate_id))
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to append event to debate {debate_id}: {exc}") from exc

    def update_status(self, debate_id: str, status: str) -> None:
        self.update_session(debate_id, status=status)

    def update_session(self, debate_id: str, status: str, target_agent: Optional[str] = None) -> None:
        try:
            with self._connection() as conn:
                if target_agent is not None:
                    conn.execute("UPDATE debates SET status = ?, target_agent = ? WHERE id = ?", (status, target_agent, debate_id))
                else:
                    conn.execute("UPDATE debates SET status = ? WHERE id = ?", (status, debate_id))
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to update session for debate {debate_id}: {exc}") from exc


    def find_all(self, user_id: Optional[str] = None, allow_unscoped: bool = False) -> List[DebateRecord]:
        if not user_id and not allow_unscoped:
            return []
        try:
            with self._connection() as conn:
                if user_id:
                    rows = conn.execute("SELECT * FROM debates WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
                else:
                    rows = conn.execute("SELECT * FROM debates ORDER BY created_at DESC").fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to fetch all debates: {exc}") from exc

        return [self._row_to_record(row) for row in rows]

    def find_by_id(self, debate_id: str, user_id: Optional[str] = None, allow_unscoped: bool = False) -> Optional[DebateRecord]:
        if not user_id and not allow_unscoped:
            return None
        try:
            with self._connection() as conn:
                if user_id:
                    row = conn.execute("SELECT * FROM debates WHERE id = ? AND user_id = ?", (debate_id, user_id)).fetchone()
                else:
                    row = conn.execute("SELECT * FROM debates WHERE id = ?", (debate_id,)).fetchone()
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to query debate {debate_id}: {exc}") from exc

        return self._row_to_record(row) if row else None

    def assign_legacy_debates_to_user(self, user_id: str) -> int:
        """Assign all pre-auth debates (user_id IS NULL) to the given user (e.g. initial admin)."""
        try:
            with self._connection() as conn:
                cursor = conn.execute("UPDATE debates SET user_id = ? WHERE user_id IS NULL", (user_id,))
                return cursor.rowcount
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to assign legacy debates to user {user_id}: {exc}") from exc

    def delete_by_user_id(self, user_id: str) -> int:
        """Delete all debates belonging to a specific user."""
        try:
            with self._connection() as conn:
                cursor = conn.execute("DELETE FROM debates WHERE user_id = ?", (user_id,))
                return cursor.rowcount
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to delete debates for user {user_id}: {exc}") from exc

    def delete(self, debate_id: str) -> None:
        try:
            with self._connection() as conn:
                conn.execute("DELETE FROM debates WHERE id = ?", (debate_id,))
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to delete debate {debate_id}: {exc}") from exc

    def _init_schema(self) -> None:
        try:
            with self._connection() as conn:
                conn.execute(_CREATE_DEBATES_TABLE)
                cursor = conn.execute("PRAGMA table_info(debates)")
                cols = [col["name"] for col in cursor.fetchall()]
                if "user_id" not in cols:
                    conn.execute("ALTER TABLE debates ADD COLUMN user_id TEXT")
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
    def _row_to_record(row: sqlite3.Row) -> DebateRecord:
        data = dict(row)
        record = DebateRecord(
            id=data["id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            user_request=data["user_request"],
            target_agent=data["target_agent"],
            status=data["status"],
            user_id=data.get("user_id"),
        )
        record.events_json = data["events_json"]
        return record
