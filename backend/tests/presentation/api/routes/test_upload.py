import os
import pytest
from fastapi.testclient import TestClient
from src.presentation.api.app import create_app
from src.presentation.api.routes.upload import TEMP_UPLOAD_DIR

@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)

def test_upload_file(client, tmp_path, monkeypatch):
    from src.presentation.api.routes import upload
    monkeypatch.setattr(upload, "TEMP_UPLOAD_DIR", str(tmp_path / "uploads"))
    
    test_content = b"fake pdf content"
    files = {"file": ("test.pdf", test_content, "application/pdf")}
    
    response = client.post("/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] == "true"
    assert data["original_filename"] == "test.pdf"
    assert "path" in data
    
    # Verify file was actually saved
    saved_path = data["path"]
    assert os.path.exists(saved_path)
    with open(saved_path, "rb") as f:
        assert f.read() == test_content

def test_upload_missing_file(client):
    response = client.post("/upload")
    assert response.status_code == 422  # Unprocessable Entity (missing field)
