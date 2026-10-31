from pathlib import Path
from unittest.mock import MagicMock
import pytest
from fastapi.testclient import TestClient
from src.presentation.api.app import create_app
from src.application.services.learn_from_session import LearnFromSession
from src.application.services.learn_from_source import LearnResult
from src.application.services.ingest_vault import IngestResult

from src.presentation.api.routes import learning

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

@pytest.fixture(autouse=True)
def mock_learning_dependencies(monkeypatch):
    from src.infrastructure.rag.in_memory_document_store import InMemoryDocumentStore
    monkeypatch.setattr(learning, "get_llm_provider", lambda _: MagicMock())
    monkeypatch.setattr(learning, "ChromaDBDocumentStore", lambda _: InMemoryDocumentStore())

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
