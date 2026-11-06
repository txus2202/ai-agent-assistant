"""
Unit tests for the images route (GET /images/{filename} and GET /api/images/{filename}).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.infrastructure.image_generation.service import ImageGenerationService
from src.presentation.api.app import create_app


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_get_image_success(client, tmp_path, monkeypatch):
    monkeypatch.setattr(ImageGenerationService, "STORAGE_DIR", tmp_path)

    test_image = tmp_path / "fidias_abc123.png"
    fake_bytes = b"\x89PNG\r\n\x1a\nfakecontent"
    test_image.write_bytes(fake_bytes)

    # Test /images/fidias_abc123.png
    resp = client.get("/images/fidias_abc123.png")
    assert resp.status_code == 200
    assert resp.content == fake_bytes
    assert "image/png" in resp.headers.get("content-type", "")

    # Test /api/images/fidias_abc123.png
    resp_api = client.get("/api/images/fidias_abc123.png")
    assert resp_api.status_code == 200
    assert resp_api.content == fake_bytes


def test_get_image_not_found(client, tmp_path, monkeypatch):
    monkeypatch.setattr(ImageGenerationService, "STORAGE_DIR", tmp_path)

    resp = client.get("/images/nonexistent_image.png")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Image not found"


def test_get_image_invalid_filename_traversal(client):
    resp = client.get("/images/..%2F..%2Fetc%2Fpasswd")
    assert resp.status_code in (400, 404)

