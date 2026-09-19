import pytest
from fastapi.testclient import TestClient
from src.presentation.api.app import create_app
from src.domain.value_objects.debate_record import DebateRecord
from src.infrastructure.persistence.sqlite_debate_repository import SqliteDebateRepository
from src.presentation.api.config import get_settings

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

@pytest.fixture
def test_repo():
    settings = get_settings()
    repo = SqliteDebateRepository(str(settings.sqlite_db_path))
    # Cleanup before test
    for record in repo.find_all():
        repo.delete(record.id)
    return repo

def test_get_empty_debates(client, test_repo):
    response = client.get("/debates")
    assert response.status_code == 200
    assert response.json() == []

def test_get_debates_with_data(client, test_repo):
    record = DebateRecord(user_request="test request", target_agent="supervisor", status="completed")
    test_repo.create(record)
    
    response = client.get("/debates")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == record.id
    assert data[0]["user_request"] == "test request"
    assert data[0]["status"] == "completed"

def test_get_single_debate(client, test_repo):
    record = DebateRecord(user_request="single", status="running")
    test_repo.create(record)
    
    response = client.get(f"/debates/{record.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == record.id
    assert data["user_request"] == "single"

def test_delete_debate(client, test_repo):
    record = DebateRecord(user_request="to_delete")
    test_repo.create(record)
    
    response = client.delete(f"/debates/{record.id}")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    
    assert test_repo.find_by_id(record.id) is None
