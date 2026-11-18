import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from src.domain.exceptions import RepositoryError
from src.domain.ports.debate_repository import IDebateRepository
from src.domain.value_objects.debate_record import (
    DebateRecord,
    DebateSummary,
    PaginatedDebateSummaries,
)
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
_METRIC_EVENT_TYPES = frozenset({"done", "agent_completed", "synthesis", "conclusion", "final_response"})
_CONCLUSION_EVENT_TYPES = frozenset({"done", "agent_completed", "message", "synthesis", "conclusion", "final_response"})
_HEADING_PREFIX_RE = re.compile(r"^#+\s*")


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

    def find_paginated_summaries(
        self,
        user_id: Optional[str] = None,
        allow_unscoped: bool = False,
        limit: int = 20,
        offset: int = 0,
        search: Optional[str] = None,
        filter_by: Optional[str] = None,
    ) -> PaginatedDebateSummaries:
        """Returns a paginated slice of lightweight DebateSummary objects."""
        safe_limit = max(1, min(limit, 100))
        safe_offset = max(0, offset)
        if not user_id and not allow_unscoped:
            return PaginatedDebateSummaries(items=[], total=0, limit=safe_limit, offset=safe_offset, total_all=0)

        where_sql, params, has_active_filter = self._build_summary_filters(
            user_id=user_id, search=search, filter_by=filter_by
        )
        try:
            with self._connection() as conn:
                total = int(
                    conn.execute(f"SELECT COUNT(*) FROM debates d WHERE {where_sql}", params).fetchone()[0]
                )
                if has_active_filter:
                    if user_id:
                        total_all = int(
                            conn.execute("SELECT COUNT(*) FROM debates WHERE user_id = ?", (user_id,)).fetchone()[0]
                        )
                    else:
                        total_all = int(conn.execute("SELECT COUNT(*) FROM debates").fetchone()[0])
                else:
                    total_all = total

                rows = conn.execute(
                    f"SELECT d.id, d.created_at, d.user_request, d.target_agent, d.status, d.user_id, d.events_json "
                    f"FROM debates d WHERE {where_sql} "
                    f"ORDER BY d.created_at DESC, d.rowid DESC LIMIT ? OFFSET ?",
                    [*params, safe_limit, safe_offset],
                ).fetchall()
                events_by_debate = self._fetch_events_for_debates(conn, [row["id"] for row in rows])
        except sqlite3.Error as exc:
            raise RepositoryError(f"Failed to fetch paginated debate summaries: {exc}") from exc

        items = [
            self._row_to_summary(row, events_by_debate.get(row["id"], []))
            for row in rows
        ]
        return PaginatedDebateSummaries(
            items=items,
            total=total,
            limit=safe_limit,
            offset=safe_offset,
            total_all=total_all,
        )

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
    def _escape_like(term: str) -> str:
        return term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    @classmethod
    def _build_summary_filters(
        cls,
        user_id: Optional[str],
        search: Optional[str],
        filter_by: Optional[str],
    ) -> tuple[str, list[Any], bool]:
        clauses: list[str] = []
        params: list[Any] = []
        has_active_filter = False

        if user_id:
            clauses.append("d.user_id = ?")
            params.append(user_id)

        normalized_filter = (filter_by or "all").strip().lower()
        if normalized_filter == "hitl":
            has_active_filter = True
            clauses.append(
                "("
                "LOWER(d.events_json) LIKE '%hitl%' "
                "OR EXISTS (SELECT 1 FROM debate_events de WHERE de.debate_id = d.id AND LOWER(de.event_json) LIKE '%hitl%')"
                ")"
            )
        elif normalized_filter in ("today", "week"):
            has_active_filter = True
            days = 1 if normalized_filter == "today" else 7
            cutoff_iso = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            clauses.append("datetime(d.created_at) >= datetime(?)")
            params.append(cutoff_iso)

        clean_search = (search or "").strip().lower()
        if clean_search:
            has_active_filter = True
            like_raw = f"%{cls._escape_like(clean_search)}%"
            if clean_search.isascii():
                clauses.append(
                    "("
                    "LOWER(d.id) LIKE ? ESCAPE '\\' "
                    "OR LOWER(d.user_request) LIKE ? ESCAPE '\\' "
                    "OR LOWER(d.events_json) LIKE ? ESCAPE '\\' "
                    "OR EXISTS (SELECT 1 FROM debate_events de WHERE de.debate_id = d.id AND LOWER(de.event_json) LIKE ? ESCAPE '\\')"
                    ")"
                )
                params.extend([like_raw, like_raw, like_raw, like_raw])
            else:
                escaped_unicode = json.dumps(clean_search)[1:-1].lower()
                like_unicode = f"%{cls._escape_like(escaped_unicode)}%"
                clauses.append(
                    "("
                    "LOWER(d.id) LIKE ? ESCAPE '\\' "
                    "OR LOWER(d.user_request) LIKE ? ESCAPE '\\' "
                    "OR LOWER(d.events_json) LIKE ? ESCAPE '\\' "
                    "OR LOWER(d.events_json) LIKE ? ESCAPE '\\' "
                    "OR EXISTS (SELECT 1 FROM debate_events de WHERE de.debate_id = d.id AND (LOWER(de.event_json) LIKE ? ESCAPE '\\' OR LOWER(de.event_json) LIKE ? ESCAPE '\\'))"
                    ")"
                )
                params.extend([like_raw, like_raw, like_raw, like_unicode, like_raw, like_unicode])

        where_sql = " AND ".join(clauses) if clauses else "1=1"
        return where_sql, params, has_active_filter

    @staticmethod
    def _parse_events_for_row(row: sqlite3.Row, event_jsons: list[str] | None = None) -> list[dict[str, Any]]:
        data = dict(row)
        combined_events: list[dict[str, Any]] = []
        legacy_raw = data.get("events_json")
        if legacy_raw and isinstance(legacy_raw, str) and legacy_raw.strip() not in ("", "[]"):
            try:
                legacy_parsed = json.loads(legacy_raw)
                if isinstance(legacy_parsed, list):
                    combined_events.extend(ev for ev in legacy_parsed if isinstance(ev, dict))
            except json.JSONDecodeError:
                pass

        for raw_ev in event_jsons or ():
            try:
                parsed = json.loads(raw_ev)
                if isinstance(parsed, dict):
                    combined_events.append(parsed)
            except json.JSONDecodeError:
                pass
        return combined_events

    @staticmethod
    def _extract_raw_tokens(ev: dict[str, Any]) -> Optional[int]:
        metadata = ev.get("metadata")
        if not isinstance(metadata, dict):
            return None
        raw_val = metadata.get("total_tokens")
        if raw_val is None or raw_val == "":
            raw_val = metadata.get("tokens")
        if raw_val is None or raw_val == "" or isinstance(raw_val, bool):
            return None
        try:
            return int(str(raw_val))
        except (TypeError, ValueError):
            return None

    @classmethod
    def _row_to_record(cls, row: sqlite3.Row, event_jsons: list[str] | None = None) -> DebateRecord:
        data = dict(row)
        record = DebateRecord(
            id=data["id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            user_request=data["user_request"],
            target_agent=data["target_agent"],
            status=data["status"],
            user_id=data.get("user_id"),
        )
        record.events = cls._parse_events_for_row(row, event_jsons)
        return record

    @classmethod
    def _row_to_summary(cls, row: sqlite3.Row, event_jsons: list[str] | None = None) -> DebateSummary:
        data = dict(row)
        events = cls._parse_events_for_row(row, event_jsons)
        prompt = data["user_request"] or ""
        total_tokens = 0
        has_hitl = False
        agents: list[str] = []
        seen_agents: set[str] = set()

        for idx, ev in enumerate(events):
            ev_type = ev.get("type")
            if isinstance(ev_type, str) and "hitl" in ev_type.lower():
                has_hitl = True

            if not prompt and ev_type == "start":
                req = ev.get("user_request")
                if isinstance(req, str) and req:
                    prompt = req

            role = ev.get("role")
            if isinstance(role, str) and role and role != "supervisor" and role not in seen_agents:
                seen_agents.add(role)
                agents.append(role)

            if not isinstance(ev_type, str) or ev_type not in _METRIC_EVENT_TYPES:
                continue

            if ev_type == "done":
                metadata = ev.get("metadata") if isinstance(ev.get("metadata"), dict) else {}
                if str(metadata.get("metrics_reported", "")).lower() == "true":
                    continue
                if idx > 0:
                    prev = events[idx - 1]
                    ev_tok = cls._extract_raw_tokens(ev)
                    prev_tok = cls._extract_raw_tokens(prev)
                    if (
                        prev.get("type") == "agent_completed"
                        and prev.get("role") == ev.get("role")
                        and ev_tok is not None
                        and ev_tok == prev_tok
                    ):
                        continue

            explicit_tokens = cls._extract_raw_tokens(ev)
            if explicit_tokens is not None and explicit_tokens > 0:
                total_tokens += explicit_tokens
            else:
                content = ev.get("content")
                if isinstance(content, str) and content.strip():
                    words = len(content.strip().split())
                    total_tokens += max(12, round(words * 1.35))

        conclusion = ""
        for ev in reversed(events):
            ev_type = ev.get("type")
            content = ev.get("content")
            if isinstance(ev_type, str) and ev_type in _CONCLUSION_EVENT_TYPES and isinstance(content, str) and content.strip():
                cleaned = _HEADING_PREFIX_RE.sub("", content.strip())
                conclusion = f"{cleaned[:160]}..." if cleaned else ""
                break

        return DebateSummary(
            id=data["id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            user_request=prompt,
            target_agent=data["target_agent"],
            status=data["status"],
            user_id=data.get("user_id"),
            event_count=len(events),
            total_tokens=total_tokens,
            has_hitl=has_hitl,
            conclusion=conclusion,
            agents=agents,
        )
