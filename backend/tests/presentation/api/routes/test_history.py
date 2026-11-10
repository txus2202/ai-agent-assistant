import pytest
from fastapi.testclient import TestClient
from src.presentation.api.app import create_app
from src.domain.entities.user import User
from src.domain.value_objects.debate_record import DebateRecord
from src.infrastructure.persistence.sqlite_debate_repository import SqliteDebateRepository
from src.presentation.api.config import get_settings
from src.presentation.api.dependencies.auth import get_current_user

@pytest.fixture
def test_user():
    return User(
        id="test-user-id",
        username="testoperator",
        password_hash="fakehash",
        is_admin=False,
        is_active=True,
    )

@pytest.fixture
def client(test_user):
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: test_user
    return TestClient(app)

@pytest.fixture
def test_repo():
    settings = get_settings()
    repo = SqliteDebateRepository(str(settings.sqlite_db_path))
    # Cleanup before test
    for record in repo.find_all(allow_unscoped=True):
        repo.delete(record.id)
    return repo

def test_debates_unauthenticated():
    raw_app = create_app()
    raw_client = TestClient(raw_app)
    response = raw_client.get("/debates")
    assert response.status_code == 401

def test_get_empty_debates(client, test_repo):
    response = client.get("/debates")
    assert response.status_code == 200
    assert response.json() == []

def test_get_debates_with_data(client, test_repo):
    record = DebateRecord(
        user_request="test request",
        target_agent="supervisor",
        status="completed",
        user_id="test-user-id",
    )
    test_repo.create(record)
    
    response = client.get("/debates")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == record.id
    assert data[0]["user_request"] == "test request"
    assert data[0]["status"] == "completed"

def test_get_single_debate(client, test_repo):
    record = DebateRecord(user_request="single", status="running", user_id="test-user-id")
    test_repo.create(record)
    
    response = client.get(f"/debates/{record.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == record.id
    assert data["user_request"] == "single"

def test_delete_debate(client, test_repo):
    record = DebateRecord(user_request="to_delete", user_id="test-user-id")
    test_repo.create(record)
    
    del_res = client.delete(f"/debates/{record.id}")
    assert del_res.status_code == 200
    assert test_repo.find_by_id(record.id) is None

def test_debate_idor_isolation_other_user(test_repo):
    # Record belongs to victim-user
    other_record = DebateRecord(user_request="private work", status="completed", user_id="victim-user")
    test_repo.create(other_record)

    # Attacker logs in
    app = create_app()
    attacker = User(id="attacker-user", username="attacker", password_hash="h", is_admin=False)
    app.dependency_overrides[get_current_user] = lambda: attacker
    client = TestClient(app)

    # Cannot view in list
    assert client.get("/debates").json() == []

    # Cannot view directly (404)
    assert client.get(f"/debates/{other_record.id}").status_code == 404

    # Cannot delete (404)
    assert client.delete(f"/debates/{other_record.id}").status_code == 404
    assert test_repo.find_by_id(other_record.id, user_id="victim-user") is not None
