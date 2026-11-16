from pathlib import Path
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from src.presentation.api.app import create_app
from src.application.services.learn_from_session import LearnFromSession
from src.application.services.learn_from_source import LearnResult
from src.application.services.ingest_vault import IngestResult

from src.domain.entities.user import User
from src.presentation.api.dependencies.auth import get_current_user

@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: User(
        id="usr-test", username="testuser", password_hash="h", is_admin=False
    )
    return TestClient(app)

def test_learning_unauthenticated():
    app = create_app()
    c = TestClient(app)
    assert c.post("/learning/session", json={"session_id": "123"}).status_code == 401


@pytest.fixture(autouse=True)
def mock_external_services(monkeypatch):
    monkeypatch.setattr("src.presentation.api.routes.learning.get_llm_provider", lambda _: MagicMock())
    monkeypatch.setattr("src.presentation.api.routes.learning.ChromaDBDocumentStore", lambda *a, **kw: MagicMock())

def test_post_learn_session(client, tmp_path, monkeypatch):
    mock_result = LearnResult(
        source="test-123",
        generated_file=tmp_path / "learned" / "2026-10-28_solucion_test.md",
        ingest_result=IngestResult(files_processed=1, chunks_upserted=3),
        errors=[]
    )

    monkeypatch.setattr(LearnFromSession, "run", lambda **kwargs: mock_result)

    payload = {
        "session_id": "test-123",
        "content": "Solución arquitectónica consensuada de autenticación con OAuth2."
    }
    response = client.post("/learning/session", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "2026-10-28_solucion_test.md" in data["file"]
    assert data["chunks_ingested"] == 3

def test_post_learn_session_error(client, monkeypatch):
    mock_result = LearnResult(
        source="empty-123",
        generated_file=None,
        errors=["Historial vacío o sin contenido para aprender."]
    )
    monkeypatch.setattr(LearnFromSession, "run", lambda **kwargs: mock_result)

    payload = {
        "session_id": "empty-123"
    }
    response = client.post("/learning/session", json=payload)
    assert response.status_code == 400
    assert "Historial vacío" in response.json()["detail"]


def test_get_domains(client, tmp_path, monkeypatch):
    mock_vault = tmp_path / "obsidian_vault"
    mock_vault.mkdir()
    (mock_vault / "01_enterprise_architecture").mkdir()
    (mock_vault / "01_enterprise_architecture" / "MOC_Enterprise_Architecture.md").write_text("# MOC")

    from src.presentation.api.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "vault_root", mock_vault)

    response = client.get("/learning/domains")
    assert response.status_code == 200
    domains = response.json()
    assert isinstance(domains, list)
    assert any(d["id"] == "01_enterprise_architecture" for d in domains)


def test_create_domain(client, tmp_path, monkeypatch):
    mock_vault = tmp_path / "obsidian_vault"
    mock_vault.mkdir()
    (mock_vault / "HOME.md").write_text("# HOME\n")

    from src.presentation.api.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "vault_root", mock_vault)

    payload = {
        "id": "04_finops",
        "name": "Cloud FinOps",
        "description": "Políticas de costes e infraestructura eficiente"
    }
    response = client.post("/learning/domains", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] == "04_finops"
    assert data["name"] == "Cloud FinOps"
    assert (mock_vault / "04_finops").is_dir()

