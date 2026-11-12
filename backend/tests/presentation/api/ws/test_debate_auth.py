import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from src.infrastructure.persistence.sqlite_user_repository import SQLiteUserRepository
from src.infrastructure.security.argon2_hasher import Argon2idPasswordHasher
from src.infrastructure.security.jwt_token_service import JwtTokenService
from src.application.services.auth_service import AuthService
from src.presentation.api.app import create_app
from src.presentation.api.config import Settings


@pytest.fixture
def auth_setup(tmp_path, monkeypatch):
    from src.infrastructure.rag.chroma_document_store import ChromaDBDocumentStore
    monkeypatch.setattr(ChromaDBDocumentStore, "__init__", lambda self, *a, **kw: None)

    db_file = str(tmp_path / "ws_auth.db")
    user_repo = SQLiteUserRepository(db_path=db_file)
    hasher = Argon2idPasswordHasher()
    token_svc = JwtTokenService(secret_key="ws_secret_key_long_enough_32_bytes_value")
    auth_service = AuthService(user_repo=user_repo, hasher=hasher, token_service=token_svc)
    settings = Settings(
        vault_path=str(tmp_path / "vault"),
        db_path=db_file,
        auth_secret_key="ws_secret_key_long_enough_32_bytes_value",
    )
    app = create_app(settings=settings, auth_service=auth_service)
    return app, auth_service, token_svc


@pytest.mark.asyncio
async def test_websocket_debate_rejected_when_initialized_and_unauthorized(auth_setup):
    app, auth_service, _ = auth_setup
    # Setup initial admin
    await auth_service.setup_initial_admin(username="wsadmin", password="password123")

    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/debate"):
            pass
    assert exc_info.value.code == 1008


@pytest.mark.asyncio
async def test_websocket_debate_rejected_when_system_not_initialized(auth_setup):
    app, _, _ = auth_setup
    # System has 0 users
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/debate"):
            pass
    assert exc_info.value.code == 1008


@pytest.mark.asyncio
async def test_websocket_wake_word_rejected_when_system_not_initialized(auth_setup):
    app, _, _ = auth_setup
    client = TestClient(app)
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/audio/wake-word"):
            pass
    assert exc_info.value.code == 1008



@pytest.mark.asyncio
async def test_websocket_debate_accepted_with_valid_cookie(auth_setup):
    app, auth_service, _ = auth_setup
    token, _ = await auth_service.setup_initial_admin(username="wsadmin", password="password123")

    client = TestClient(app, cookies={"atenea_session": token})
    with client.websocket_connect("/ws/debate") as ws:
        ws.send_json({"type": "not_start"})
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "Expected 'start'" in msg["content"]


@pytest.mark.asyncio
async def test_websocket_origin_allowed_for_same_origin(auth_setup):
    app, auth_service, _ = auth_setup
    token, _ = await auth_service.setup_initial_admin(username="wsadmin", password="password123")

    client = TestClient(app, cookies={"atenea_session": token})
    # Same-origin request (Tailscale or domain host matches Origin)
    headers = {
        "origin": "https://n100-lab.taild9f14f.ts.net",
        "host": "n100-lab.taild9f14f.ts.net",
    }
    with client.websocket_connect("/ws/debate", headers=headers) as ws:
        ws.send_json({"type": "not_start"})
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "Expected 'start'" in msg["content"]


@pytest.mark.asyncio
async def test_websocket_origin_allowed_via_x_forwarded_host(auth_setup):
    app, auth_service, _ = auth_setup
    token, _ = await auth_service.setup_initial_admin(username="wsadmin", password="password123")

    client = TestClient(app, cookies={"atenea_session": token})
    # Reverse proxy behind Tailscale or Nginx
    headers = {
        "origin": "https://n100-lab.taild9f14f.ts.net",
        "x-forwarded-host": "n100-lab.taild9f14f.ts.net",
        "host": "localhost:8000",
    }
    with client.websocket_connect("/ws/debate", headers=headers) as ws:
        ws.send_json({"type": "not_start"})
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "Expected 'start'" in msg["content"]


@pytest.mark.asyncio
async def test_websocket_origin_rejected_for_disallowed_cross_site_origin(auth_setup):
    app, auth_service, _ = auth_setup
    token, _ = await auth_service.setup_initial_admin(username="wsadmin", password="password123")

    client = TestClient(app, cookies={"atenea_session": token})
    # Untrusted cross-site origin attempt (CSWSH)
    headers = {
        "origin": "https://attacker.evil.com",
        "host": "localhost:8000",
    }
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws/debate", headers=headers):
            pass
    assert exc_info.value.code == 1008
