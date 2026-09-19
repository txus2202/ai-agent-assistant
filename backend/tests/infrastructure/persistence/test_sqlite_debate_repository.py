import json
import pytest
from datetime import datetime
from src.domain.value_objects.debate_record import DebateRecord
from src.infrastructure.persistence.sqlite_debate_repository import SqliteDebateRepository

@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "test_debate.db"
    return SqliteDebateRepository(str(db_path))

def test_create_and_find(repo):
    record = DebateRecord(user_request="test request", target_agent="supervisor", status="running")
    record.events_json = json.dumps([{"type": "start"}])
    repo.create(record)
    
    found = repo.find_by_id(record.id)
    assert found is not None
    assert found.user_request == "test request"
    assert found.status == "running"
    assert len(found.events) == 1

def test_append_event(repo):
    record = DebateRecord(user_request="test", status="running")
    repo.create(record)
    
    repo.append_event(record.id, json.dumps({"type": "msg1"}))
    repo.append_event(record.id, json.dumps({"type": "msg2"}))
    
    found = repo.find_by_id(record.id)
    assert len(found.events) == 2
    assert found.events[0]["type"] == "msg1"
    assert found.events[1]["type"] == "msg2"

def test_update_status(repo):
    record = DebateRecord(user_request="test", status="running")
    repo.create(record)
    
    repo.update_status(record.id, "completed")
    
    found = repo.find_by_id(record.id)
    assert found.status == "completed"

def test_find_all_and_delete(repo):
    repo.create(DebateRecord(user_request="test1"))
    repo.create(DebateRecord(user_request="test2"))
    
    all_debates = repo.find_all()
    assert len(all_debates) == 2
    
    repo.delete(all_debates[0].id)
    
    all_debates_after = repo.find_all()
    assert len(all_debates_after) == 1
