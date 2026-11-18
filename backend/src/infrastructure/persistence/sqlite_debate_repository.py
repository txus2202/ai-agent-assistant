import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, List, Optional

from src.domain.exceptions import RepositoryError
from src.domain.ports.debate_repository import IDebateRepository
from src.domain.value_objects.debate_record import DebateRecord
from src.infrastructure.persistence.sqlite_base import SqliteConnectionManager

_CREATE_DEBATES_TABLE = """
    CREATE TABLE IF NOT EXISTS debates (
        id            TEXT PRIMARY KEY,
        created_at    TEXT NOT NULL,
        user_request  TEXT NOT NULL,
        target_agent  TEXT NOT NULL,
        events_json   TEXT NOT NULL DEFAULT '[]',
        status        TEXT NOT NULL,
        user_id       TEXT
    )
"""

_CREATE_DEBATE_EVENTS_TABLE = """
    CREATE TABLE IF NOT EXISTS debate_events (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        debate_id   TEXT NOT NULL,
        seq         INTEGER NOT NULL,
        event_json  TEXT NOT NULL,
        created_at  TEXT NOT NULL,
        FOREIGN KEY (debate_id) REFERENCES debates(id) ON DELETE CASCADE
    )
"""

_CREATE_DEBATE_EVENTS_INDEX = """
    CREATE INDEX IF NOT EXISTS idx_debate_events_debate_seq
        ON debate_events(debate_id, seq)
"""

_EVENT_QUERY_CHUNK_SIZE = 500


class SqliteDebateRepository(IDebateRepository, SqliteConnectionManager):
    def __init__(self, db_path: str) -> None:
        SqliteConnectionManager.__init__(self, db_path)
        self._init_schema()

    def create(self, debate: DebateRecord) -> None:
        created_iso = debate.created_at.isoformat()
        initial_events = debate.events
        try:
            with self._connection() as conn:
                conn.execute(
                    "INSERT INTO debates (id, created_at, user_request, target_agent, events_json, status, user_id) "
                    "VALUES (?, ?, ?, ?, '[]', ?, ?)",
                    (
                        debate.id,
                        created_iso,
                        debate.user_request,
                        debate.target_agent,
                        debate.status,
                        debate.user_id,
                    ),
                )
                if initial_events:
                    conn.executemany(
                        "INSERT INTO debate_events (debate_id, seq, event_json, created_at) VALUES (?, ?, ?, ?)",
                        [
                            (debate.id, idx, json.dumps(ev), created_iso)
                            for idx, ev in enumerate(initial_events)
                        ],
                    )
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to create debate {debate.id}: {exc}") from exc

    def append_event(self, debate_id: str, event_json: str) -> None:
        """O(1) append-only insert into normalized ``debate_events`` under BEGIN IMMEDIATE."""
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            with self._connection() as conn:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT events_json, created_at FROM debates WHERE id = ?",
                    (debate_id,),
                ).fetchone()
                if not row:
                    return

                legacy_raw = row["events_json"]
                if legacy_raw and legacy_raw.strip() not in ("", "[]"):
                    next_seq = self._migrate_legacy_events_for_row(
                        conn, debate_id, legacy_raw, row["created_at"]
                    )
                else:
                    seq_row = conn.execute(
                        "SELECT COALESCE(MAX(seq), -1) + 1 AS next_seq FROM debate_events WHERE debate_id = ?",
                        (debate_id,),
                    ).fetchone()
                    next_seq = int(seq_row["next_seq"]) if seq_row else 0

                conn.execute(
                    "INSERT INTO debate_events (debate_id, seq, event_json, created_at) VALUES (?, ?, ?, ?)",
                    (debate_id, next_seq, event_json, now_iso),
                )
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to append event to debate {debate_id}: {exc}") from exc

    def update_status(self, debate_id: str, status: str) -> None:
        self.update_session(debate_id, status=status)

    def update_session(self, debate_id: str, status: str, target_agent: Optional[str] = None) -> None:
        try:
            with self._connection() as conn:
                if target_agent is not None:
                    conn.execute(
                        "UPDATE debates SET status = ?, target_agent = ? WHERE id = ?",
                        (status, target_agent, debate_id),
                    )
                else:
                    conn.execute(
                        "UPDATE debates SET status = ? WHERE id = ?",
                        (status, debate_id),
                    )
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to update session for debate {debate_id}: {exc}") from exc

    def find_all(self, user_id: Optional[str] = None, allow_unscoped: bool = False) -> List[DebateRecord]:
        if not user_id and not allow_unscoped:
            return []
        try:
            with self._connection() as conn:
                if user_id:
                    rows = conn.execute(
                        "SELECT * FROM debates WHERE user_id = ? ORDER BY created_at DESC",
                        (user_id,),
                    ).fetchall()
                else:
                    rows = conn.execute("SELECT * FROM debates ORDER BY created_at DESC").fetchall()
                events_by_debate = self._fetch_events_for_debates(conn, [row["id"] for row in rows])
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to fetch all debates: {exc}") from exc

        return [
            self._row_to_record(row, events_by_debate.get(row["id"], []))
            for row in rows
        ]

    def find_by_id(
        self, debate_id: str, user_id: Optional[str] = None, allow_unscoped: bool = False
    ) -> Optional[DebateRecord]:
        if not user_id and not allow_unscoped:
            return None
        try:
            with self._connection() as conn:
                if user_id:
                    row = conn.execute(
                        "SELECT * FROM debates WHERE id = ? AND user_id = ?",
                        (debate_id, user_id),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT * FROM debates WHERE id = ?",
                        (debate_id,),
                    ).fetchone()
                if not row:
                    return None
                ev_rows = conn.execute(
                    "SELECT event_json FROM debate_events WHERE debate_id = ? ORDER BY seq ASC, id ASC",
                    (debate_id,),
                ).fetchall()
                event_jsons = [ev_row["event_json"] for ev_row in ev_rows]
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to query debate {debate_id}: {exc}") from exc

        return self._row_to_record(row, event_jsons)

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
                conn.execute(
                    "DELETE FROM debate_events WHERE debate_id IN (SELECT id FROM debates WHERE user_id = ?)",
                    (user_id,),
                )
                cursor = conn.execute("DELETE FROM debates WHERE user_id = ?", (user_id,))
                return cursor.rowcount
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to delete debates for user {user_id}: {exc}") from exc

    def delete(self, debate_id: str) -> None:
        try:
            with self._connection() as conn:
                conn.execute("DELETE FROM debate_events WHERE debate_id = ?", (debate_id,))
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

                conn.execute(_CREATE_DEBATE_EVENTS_TABLE)
                conn.execute(_CREATE_DEBATE_EVENTS_INDEX)

                legacy_rows = conn.execute(
                    "SELECT id, events_json, created_at FROM debates "
                    "WHERE events_json IS NOT NULL AND TRIM(events_json) NOT IN ('', '[]')"
                ).fetchall()
                for legacy_row in legacy_rows:
                    self._migrate_legacy_events_for_row(
                        conn,
                        legacy_row["id"],
                        legacy_row["events_json"],
                        legacy_row["created_at"],
                    )
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to initialise schema: {exc}") from exc

    @staticmethod
    def _migrate_legacy_events_for_row(
        conn: sqlite3.Connection,
        debate_id: str,
        legacy_raw: str,
        created_at: str,
    ) -> int:
        seq_row = conn.execute(
            "SELECT COALESCE(MAX(seq), -1) + 1 AS next_seq FROM debate_events WHERE debate_id = ?",
            (debate_id,),
        ).fetchone()
        next_seq = int(seq_row["next_seq"]) if seq_row else 0

        parsed: Any = []
        try:
            parsed = json.loads(legacy_raw)
        except json.JSONDecodeError:
            parsed = []

        if isinstance(parsed, list) and parsed:
            conn.executemany(
                "INSERT INTO debate_events (debate_id, seq, event_json, created_at) VALUES (?, ?, ?, ?)",
                [
                    (debate_id, next_seq + offset, json.dumps(ev), created_at)
                    for offset, ev in enumerate(parsed)
                ],
            )
            next_seq += len(parsed)

        conn.execute("UPDATE debates SET events_json = '[]' WHERE id = ?", (debate_id,))
        return next_seq

    @staticmethod
    def _fetch_events_for_debates(
        conn: sqlite3.Connection, debate_ids: List[str]
    ) -> dict[str, list[str]]:
        events_by_debate: dict[str, list[str]] = {did: [] for did in debate_ids}
        for start in range(0, len(debate_ids), _EVENT_QUERY_CHUNK_SIZE):
            batch = debate_ids[start : start + _EVENT_QUERY_CHUNK_SIZE]
            placeholders = ",".join("?" for _ in batch)
            ev_rows = conn.execute(
                f"SELECT debate_id, event_json FROM debate_events "
                f"WHERE debate_id IN ({placeholders}) ORDER BY seq ASC, id ASC",
                batch,
            ).fetchall()
            for ev_row in ev_rows:
                events_by_debate[ev_row["debate_id"]].append(ev_row["event_json"])
        return events_by_debate

    @staticmethod
    def _row_to_record(row: sqlite3.Row, event_jsons: list[str] | None = None) -> DebateRecord:
        data = dict(row)
        record = DebateRecord(
            id=data["id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            user_request=data["user_request"],
            target_agent=data["target_agent"],
            status=data["status"],
            user_id=data.get("user_id"),
        )
        combined_events: list[dict[str, Any]] = []
        legacy_raw = data.get("events_json")
        if legacy_raw and isinstance(legacy_raw, str) and legacy_raw.strip() not in ("", "[]"):
            try:
                legacy_parsed = json.loads(legacy_raw)
                if isinstance(legacy_parsed, list):
                    combined_events.extend(legacy_parsed)
            except json.JSONDecodeError:
                pass

        for raw_ev in event_jsons or ():
            combined_events.append(json.loads(raw_ev))

        record.events = combined_events
        return record
