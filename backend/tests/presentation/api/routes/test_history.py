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
    assert response.json() == {
        "total": 0,
        "total_all": 0,
        "limit": 20,
        "offset": 0,
        "items": [],
    }

def test_get_debates_with_data(client, test_repo):
    record = DebateRecord(
        user_request="test request",
        target_agent="supervisor",
        status="completed",
        user_id="test-user-id",
        events=[
            {"type": "start", "user_request": "test request"},
            {"type": "hitl_required", "role": "Hermes", "content": "Aprobar alcance"},
            {
                "type": "agent_completed",
                "role": "Hermes",
                "content": "Alcance ok",
                "metadata": {"total_tokens": "120", "tokens": "120"},
            },
            {
                "type": "done",
                "role": "Hermes",
                "content": "Alcance ok",
                "metadata": {"metrics_reported": "true"},
            },
            {
                "type": "done",
                "role": "supervisor",
                "content": "# Dictamen final consolidado",
                "metadata": {"total_tokens": "80", "tokens": "80"},
            },
        ],
    )
    test_repo.create(record)

    response = client.get("/debates")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["total_all"] == 1
    assert data["limit"] == 20
    assert data["offset"] == 0
    assert len(data["items"]) == 1

    summary = data["items"][0]
    assert summary["id"] == record.id
    assert summary["user_request"] == "test request"
    assert summary["status"] == "completed"
    assert "events" not in summary
    assert summary["event_count"] == 5
    assert summary["total_tokens"] == 200
    assert summary["has_hitl"] is True
    assert summary["agents"] == ["Hermes"]
    assert "Dictamen final consolidado" in summary["conclusion"]

def test_get_debates_pagination_and_filters(client, test_repo):
    from datetime import datetime, timedelta, timezone

    base_time = datetime(2026, 11, 18, 12, 0, tzinfo=timezone.utc)
    for idx in range(5):
        events = [{"type": "start", "user_request": f"Prompt {idx}"}]
        if idx % 2 == 0:
            events.append({"type": "hitl_required", "role": "Hermes", "content": "Check"})
        test_repo.create(
            DebateRecord(
                id=f"deb-page-{idx}",
                created_at=base_time + timedelta(minutes=idx),
                user_request=f"Prompt {idx}" + (" arquitectura" if idx == 4 else ""),
                status="completed",
                user_id="test-user-id",
                events=events,
            )
        )

    page_res = client.get("/debates?limit=2&offset=1").json()
    assert page_res["total"] == 5
    assert page_res["total_all"] == 5
    assert page_res["limit"] == 2
    assert page_res["offset"] == 1
    # Ordered DESC by created_at: idx 4, 3, 2, 1, 0 -> offset 1, limit 2 returns 3 and 2
    assert [item["id"] for item in page_res["items"]] == ["deb-page-3", "deb-page-2"]
    assert all("events" not in item for item in page_res["items"])

    hitl_res = client.get("/debates?filter=hitl").json()
    assert hitl_res["total"] == 3
    assert hitl_res["total_all"] == 5
    assert [item["id"] for item in hitl_res["items"]] == ["deb-page-4", "deb-page-2", "deb-page-0"]

    search_res = client.get("/debates?search=arquitectura").json()
    assert search_res["total"] == 1
    assert search_res["total_all"] == 5
    assert search_res["items"][0]["id"] == "deb-page-4"

    # Full detail endpoint still returns full events on demand
    detail_res = client.get("/debates/deb-page-4")
    assert detail_res.status_code == 200
    assert len(detail_res.json()["events"]) == 2

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
    list_res = client.get("/debates").json()
    assert list_res["items"] == []
    assert list_res["total"] == 0

    # Cannot view directly (404)
    assert client.get(f"/debates/{other_record.id}").status_code == 404

    # Cannot delete (404)
    assert client.delete(f"/debates/{other_record.id}").status_code == 404
    assert test_repo.find_by_id(other_record.id, user_id="victim-user") is not None
