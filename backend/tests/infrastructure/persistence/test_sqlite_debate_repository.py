import json
import pytest
from datetime import datetime
from src.domain.value_objects.debate_record import DebateRecord
from src.infrastructure.persistence.sqlite_debate_repository import SqliteDebateRepository


@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "test_debate.db"
    return SqliteDebateRepository(str(db_path))


def test_create_and_find_scoped(repo):
    record = DebateRecord(user_request="test request", target_agent="supervisor", status="running", user_id="usr-test-1")
    record.events_json = json.dumps([{"type": "start"}])
    repo.create(record)

    # Scoped search succeeds
    found = repo.find_by_id(record.id, user_id="usr-test-1")
    assert found is not None
    assert found.user_request == "test request"
    assert found.status == "running"
    assert len(found.events) == 1

    # Unscoped without explicit allow_unscoped fails-closed
    assert repo.find_by_id(record.id) is None
    # Unscoped with allow_unscoped succeeds
    assert repo.find_by_id(record.id, allow_unscoped=True) is not None


def test_append_event(repo):
    record = DebateRecord(user_request="test", status="running", user_id="usr-test-1")
    repo.create(record)

    repo.append_event(record.id, json.dumps({"type": "msg1"}))
    repo.append_event(record.id, json.dumps({"type": "msg2"}))

    found = repo.find_by_id(record.id, user_id="usr-test-1")
    assert found is not None
    assert len(found.events) == 2
    assert found.events[0]["type"] == "msg1"
    assert found.events[1]["type"] == "msg2"


def test_update_status(repo):
    record = DebateRecord(user_request="test", status="running", user_id="usr-test-1")
    repo.create(record)

    repo.update_status(record.id, "completed")

    found = repo.find_by_id(record.id, user_id="usr-test-1")
    assert found is not None
    assert found.status == "completed"


def test_find_all_fail_closed_and_delete(repo):
    repo.create(DebateRecord(user_request="test1", user_id="usr-a"))
    repo.create(DebateRecord(user_request="test2", user_id="usr-b"))

    # Fail closed without user_id and without allow_unscoped
    assert repo.find_all() == []

    # Scoped queries return only respective user records
    debates_a = repo.find_all(user_id="usr-a")
    assert len(debates_a) == 1
    assert debates_a[0].user_id == "usr-a"

    # Admin unscoped returns all
    all_debates = repo.find_all(allow_unscoped=True)
    assert len(all_debates) == 2

    # Delete
    repo.delete(debates_a[0].id)
    assert repo.find_all(user_id="usr-a") == []
    assert len(repo.find_all(allow_unscoped=True)) == 1


def test_assign_legacy_debates_to_user(repo):
    # Pre-auth debates with user_id=None
    repo.create(DebateRecord(user_request="legacy1", user_id=None))
    repo.create(DebateRecord(user_request="legacy2", user_id=None))

    assigned = repo.assign_legacy_debates_to_user("admin-1")
    assert assigned == 2

    # Now they belong to admin-1
    admin_debates = repo.find_all(user_id="admin-1")
    assert len(admin_debates) == 2


def test_delete_by_user_id(repo):
    repo.create(DebateRecord(user_request="user1_req", user_id="to-purge"))
    repo.create(DebateRecord(user_request="user2_req", user_id="other"))

    purged = repo.delete_by_user_id("to-purge")
    assert purged == 1
    assert repo.find_all(user_id="to-purge") == []
    assert len(repo.find_all(user_id="other")) == 1


def test_wal_mode_enabled_and_connection_closed_on_exception(tmp_path, monkeypatch):
    import sqlite3
    import src.infrastructure.persistence.sqlite_base as sqlite_base_mod
    from src.infrastructure.persistence.sqlite_base import SqliteConnectionManager

    db_path = str(tmp_path / "wal_check.db")
    SqliteDebateRepository(db_path)

    with sqlite3.connect(db_path) as check_conn:
        mode = check_conn.execute("PRAGMA journal_mode").fetchone()[0]
    check_conn.close()
    assert str(mode).lower() == "wal"

    closed_flags: list[bool] = []
    orig_connect = sqlite3.connect

    def _tracking_connect(*args, **kwargs):
        real_conn = orig_connect(*args, **kwargs)

        class _ConnWrapper:
            def __getattr__(self, name):
                return getattr(real_conn, name)

            def close(self):
                closed_flags.append(True)
                return real_conn.close()

        return _ConnWrapper()

    mgr = SqliteConnectionManager(db_path)
    monkeypatch.setattr(sqlite_base_mod.sqlite3, "connect", _tracking_connect)
    with pytest.raises(RuntimeError, match="boom"):
        with mgr.connection() as conn:
            conn.execute("SELECT 1")
            raise RuntimeError("boom")

    assert closed_flags == [True]


def test_append_event_uses_normalized_debate_events_o1_and_handles_concurrency(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    import sqlite3

    db_path = str(tmp_path / "events_o1.db")
    repo = SqliteDebateRepository(db_path)
    record = DebateRecord(user_request="concurrent", status="running", user_id="usr-1")
    repo.create(record)

    def _append_worker(idx: int) -> None:
        repo.append_event(record.id, json.dumps({"type": "msg", "seq_tag": idx}))

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(_append_worker, i) for i in range(20)]
        for fut in futures:
            fut.result(timeout=5.0)

    found = repo.find_by_id(record.id, user_id="usr-1")
    assert found is not None
    assert len(found.events) == 20
    assert {ev["seq_tag"] for ev in found.events} == set(range(20))

    with sqlite3.connect(db_path) as conn:
        blob = conn.execute("SELECT events_json FROM debates WHERE id = ?", (record.id,)).fetchone()[0]
        event_rows = conn.execute(
            "SELECT seq, event_json FROM debate_events WHERE debate_id = ? ORDER BY seq ASC",
            (record.id,),
        ).fetchall()
    conn.close()
    assert blob == "[]"
    assert [r[0] for r in event_rows] == list(range(20))


def test_legacy_events_json_migrated_and_backwards_compatible(tmp_path):
    import sqlite3

    db_path = str(tmp_path / "legacy_debates.db")
    legacy_conn = sqlite3.connect(db_path)
    legacy_conn.execute(
        """
        CREATE TABLE debates (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            user_request TEXT NOT NULL,
            target_agent TEXT NOT NULL,
            events_json TEXT NOT NULL,
            status TEXT NOT NULL,
            user_id TEXT
        )
        """
    )
    legacy_conn.execute(
        "INSERT INTO debates (id, created_at, user_request, target_agent, events_json, status, user_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "legacy-1",
            "2026-01-01T10:00:00+00:00",
            "legacy query",
            "supervisor",
            json.dumps([{"type": "old1"}, {"type": "old2"}]),
            "running",
            "usr-legacy",
        ),
    )
    legacy_conn.commit()
    legacy_conn.close()

    repo = SqliteDebateRepository(db_path)
    found_before = repo.find_by_id("legacy-1", user_id="usr-legacy")
    assert found_before is not None
    assert [e["type"] for e in found_before.events] == ["old1", "old2"]

    repo.append_event("legacy-1", json.dumps({"type": "new3"}))
    found_after = repo.find_by_id("legacy-1", user_id="usr-legacy")
    assert found_after is not None
    assert [e["type"] for e in found_after.events] == ["old1", "old2", "new3"]

    # Deleting debate also removes normalized debate_events rows
    repo.delete("legacy-1")
    check_conn = sqlite3.connect(db_path)
    remaining = check_conn.execute("SELECT COUNT(*) FROM debate_events WHERE debate_id = 'legacy-1'").fetchone()[0]
    check_conn.close()
    assert remaining == 0


def test_find_paginated_summaries_slices_pages_and_avoids_overfetching(repo, monkeypatch):
    from datetime import timedelta, timezone

    now = datetime.now(timezone.utc)
    for i in range(5):
        rec = DebateRecord(
            id=f"sum-{i}",
            created_at=now - timedelta(days=i * 3),
            user_request=f"Auditoría sesión {i}",
            status="completed",
            user_id="usr-1",
            events=[
                {"type": "start", "user_request": f"Auditoría sesión {i}"},
                {
                    "type": "agent_completed",
                    "role": "senior_architect",
                    "content": f"Conclusión {i}",
                    "metadata": {"total_tokens": str(100 + i)},
                },
            ],
        )
        repo.create(rec)
    repo.create(DebateRecord(id="sum-other", user_request="Secret", user_id="usr-other"))

    # Fail-closed when user_id is omitted without allow_unscoped
    empty_page = repo.find_paginated_summaries(limit=2, offset=0)
    assert empty_page.items == []
    assert empty_page.total == 0

    fetched_batches: list[list[str]] = []
    orig_fetch = repo._fetch_events_for_debates

    def _spy_fetch(conn, debate_ids):
        fetched_batches.append(list(debate_ids))
        return orig_fetch(conn, debate_ids)

    monkeypatch.setattr(repo, "_fetch_events_for_debates", _spy_fetch)

    page = repo.find_paginated_summaries(user_id="usr-1", limit=2, offset=1)
    assert page.total == 5
    assert page.total_all == 5
    assert [item.id for item in page.items] == ["sum-1", "sum-2"]
    assert fetched_batches == [["sum-1", "sum-2"]]
    assert page.items[0].total_tokens == 101
    assert page.items[0].agents == ["senior_architect"]
    assert page.items[0].event_count == 2

    week_page = repo.find_paginated_summaries(user_id="usr-1", filter_by="week")
    assert [item.id for item in week_page.items] == ["sum-0", "sum-1", "sum-2"]
    assert week_page.total_all == 5

    today_page = repo.find_paginated_summaries(user_id="usr-1", filter_by="today")
    assert [item.id for item in today_page.items] == ["sum-0"]

    accent_search = repo.find_paginated_summaries(user_id="usr-1", search="Auditoría sesión 3")
    assert [item.id for item in accent_search.items] == ["sum-3"]
