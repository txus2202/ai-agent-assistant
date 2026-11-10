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
