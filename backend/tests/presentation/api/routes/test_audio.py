import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from src.presentation.api.app import create_app
from src.infrastructure.audio.local_audio_service import LocalAudioService


from src.domain.entities.user import User
from src.presentation.api.dependencies.auth import get_current_user


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: User(
        id="usr-test", username="testuser", password_hash="h", is_admin=False
    )
    return TestClient(app)


def test_audio_unauthenticated():
    app = create_app()
    c = TestClient(app)
    assert c.post("/audio/transcribe").status_code == 401
    assert c.post("/audio/synthesize", json={"text": "hi"}).status_code == 401


@pytest.fixture
def mock_audio_service():
    with patch("src.presentation.api.routes.audio.get_audio_service") as mock_get:
        service = AsyncMock(spec=LocalAudioService)
        mock_get.return_value = service
        yield service


def test_transcribe_audio_success(client, mock_audio_service):
    mock_audio_service.transcribe_audio.return_value = "Hola probando"
    
    response = client.post(
        "/audio/transcribe",
        files={"file": ("test.wav", b"fakeaudiobytes", "audio/wav")}
    )
    
    assert response.status_code == 200
    assert response.json() == {"text": "Hola probando"}
    mock_audio_service.transcribe_audio.assert_called_once()


def test_transcribe_audio_missing_file(client):
    response = client.post("/audio/transcribe")
    assert response.status_code == 422 # Unprocessable entity (FastAPI default for missing file)


def test_synthesize_audio_success(client, mock_audio_service):
    mock_audio_service.synthesize_speech.return_value = b"fakeaudiobytes"
    
    response = client.post(
        "/audio/synthesize",
        json={"text": "Hola mundo"}
    )
    
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == b"fakeaudiobytes"
    mock_audio_service.synthesize_speech.assert_called_once_with("Hola mundo")


def test_synthesize_audio_missing_text(client):
    response = client.post("/audio/synthesize", json={"notext": "algo"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Text is required"
