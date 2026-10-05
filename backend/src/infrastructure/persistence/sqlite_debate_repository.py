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
        status        TEXT NOT NULL
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
                    "INSERT INTO debates (id, created_at, user_request, target_agent, events_json, status) VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        debate.id,
                        debate.created_at.isoformat(),
                        debate.user_request,
                        debate.target_agent,
                        debate.events_json,
                        debate.status,
                    ),
                )
        except sqlite3.Error as exc:
            import logging
            log = logging.getLogger(__name__)
            log.error(f"DEBUG SQLITE CREATE: id={type(debate.id)} created_at={type(debate.created_at.isoformat())} user_request={type(debate.user_request)} target_agent={type(debate.target_agent)} events_json={type(debate.events_json)} status={type(debate.status)}")
            log.error(f"DEBUG SQLITE CREATE VALUES: target_agent={debate.target_agent}")
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
        try:
            with self._connection() as conn:
                conn.execute("UPDATE debates SET status = ? WHERE id = ?", (status, debate_id))
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to update status for debate {debate_id}: {exc}") from exc

    def find_all(self) -> List[DebateRecord]:
        try:
            with self._connection() as conn:
                rows = conn.execute("SELECT * FROM debates ORDER BY created_at DESC").fetchall()
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to fetch all debates: {exc}") from exc

        return [self._row_to_record(row) for row in rows]

    def find_by_id(self, debate_id: str) -> Optional[DebateRecord]:
        try:
            with self._connection() as conn:
                row = conn.execute("SELECT * FROM debates WHERE id = ?", (debate_id,)).fetchone()
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to query debate {debate_id}: {exc}") from exc

        return self._row_to_record(row) if row else None

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
        record = DebateRecord(
            id=row["id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            user_request=row["user_request"],
            target_agent=row["target_agent"],
            status=row["status"],
        )
        record.events_json = row["events_json"]
        return record
