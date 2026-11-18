import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.domain.entities.user import User
from src.presentation.api.app import create_app
from src.presentation.api.config import Settings, get_settings
from src.presentation.api.dependencies.auth import get_current_user
from src.presentation.api.routes import upload


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(upload, "TEMP_UPLOAD_DIR", str(tmp_path / "uploads"))
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: User(
        id="usr-test", username="testuser", password_hash="h", is_admin=False
    )
    return TestClient(app)


def test_upload_unauthenticated():
    app = create_app()
    c = TestClient(app)
    assert c.post("/upload").status_code == 401


def test_upload_file(client, tmp_path):
    test_content = b"fake pdf content"
    files = {"file": ("test.pdf", test_content, "application/pdf")}

    response = client.post("/upload", files=files)
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["original_filename"] == "test.pdf"
    assert "attachment_id" in data
    assert "path" in data

    saved_path = Path(data["path"])
    assert saved_path.exists()
    assert saved_path.is_relative_to(upload.get_user_upload_dir("usr-test"))
    assert saved_path.name == data["attachment_id"]
    assert saved_path.read_bytes() == test_content


def test_upload_missing_file(client):
    response = client.post("/upload")
    assert response.status_code == 422


def test_upload_respects_settings_max_learn_file_mb(tmp_path, monkeypatch):
    monkeypatch.setattr(upload, "TEMP_UPLOAD_DIR", str(tmp_path / "uploads"))
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: User(
        id="usr-limit", username="limituser", password_hash="h", is_admin=False
    )
    app.dependency_overrides[get_settings] = lambda: Settings(
        sqlite_db_path=tmp_path / "sqlite.db",
        auth_secret_key="test_secret_key_32_bytes_minimum_length",
        max_learn_file_mb=1,
    )
    c = TestClient(app)

    oversized = b"x" * (1024 * 1024 + 64)
    response = c.post("/upload", files={"file": ("big.pdf", oversized, "application/pdf")})
    assert response.status_code == 413
    assert "1MB" in response.json()["detail"]

    user_dir = upload.get_user_upload_dir("usr-limit")
    assert list(user_dir.iterdir()) == []


def test_resolve_user_attachment_path_blocks_traversal_and_cross_user(tmp_path, monkeypatch):
    monkeypatch.setattr(upload, "TEMP_UPLOAD_DIR", str(tmp_path / "uploads"))
    user_a_dir = upload.get_user_upload_dir("usr-a")
    user_b_dir = upload.get_user_upload_dir("usr-b")
    user_a_dir.mkdir(parents=True, exist_ok=True)
    user_b_dir.mkdir(parents=True, exist_ok=True)

    valid_file = user_a_dir / "doc_123.pdf"
    valid_file.write_bytes(b"ok")
    other_file = user_b_dir / "secret.pdf"
    other_file.write_bytes(b"secret")

    assert upload.resolve_user_attachment_path("doc_123.pdf", "usr-a") == valid_file.resolve()
    assert upload.resolve_user_attachment_path(str(valid_file), "usr-a") == valid_file.resolve()

    for bad in (
        "../usr-b/secret.pdf",
        "../../.env",
        "..",
        ".",
        str(other_file),
        "/etc/passwd",
        "file:///etc/passwd",
        "doc\x00.pdf",
        "",
    ):
        with pytest.raises((ValueError, PermissionError)):
            upload.resolve_user_attachment_path(bad, "usr-a")

    with pytest.raises(PermissionError):
        upload.resolve_user_attachment_path("doc_123.pdf", None)
