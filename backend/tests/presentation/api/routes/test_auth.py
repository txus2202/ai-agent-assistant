import pytest
from httpx import AsyncClient, ASGITransport
from src.infrastructure.persistence.sqlite_user_repository import SQLiteUserRepository
from src.infrastructure.security.argon2_hasher import Argon2idPasswordHasher
from src.infrastructure.security.jwt_token_service import JwtTokenService
from src.application.services.auth_service import AuthService
from src.presentation.api.app import create_app
from src.presentation.api.config import Settings


@pytest.fixture
def auth_components(tmp_path):
    db_file = str(tmp_path / "auth_test.db")
    user_repo = SQLiteUserRepository(db_path=db_file)
    hasher = Argon2idPasswordHasher()
    token_svc = JwtTokenService(secret_key="test_auth_secret_key_32_bytes_long_entropy")
    auth_service = AuthService(user_repo=user_repo, hasher=hasher, token_service=token_svc)
    return user_repo, auth_service


@pytest.fixture
def test_app(auth_components, tmp_path):
    from src.presentation.api.dependencies.rate_limiter import default_rate_limiter
    default_rate_limiter.reset()

    user_repo, auth_service = auth_components
    settings = Settings(
        vault_path=str(tmp_path / "vault"),
        db_path=str(tmp_path / "auth_test.db"),
        auth_secret_key="test_auth_secret_key_32_bytes_long_entropy",
    )
    app = create_app(settings=settings, auth_service=auth_service)
    return app


@pytest.mark.asyncio
async def test_auth_status_uninitialized(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/auth/status")
        assert res.status_code == 200
        data = res.json()
        assert data["initialized"] is False
        assert data["authenticated"] is False
        assert data["user"] is None


@pytest.mark.asyncio
async def test_initial_setup_and_login_flow(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Setup first admin
        setup_res = await client.post(
            "/api/auth/setup",
            json={"username": "superadmin", "password": "SuperSecretPassword123!"},
        )
        assert setup_res.status_code == 200
        setup_data = setup_res.json()
        assert setup_data["user"]["username"] == "superadmin"
        assert setup_data["user"]["is_admin"] is True
        assert "atenea_session" in setup_res.cookies

        # 2. Status should now be initialized and authenticated
        status_res = await client.get("/api/auth/status")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["initialized"] is True
        assert status_data["authenticated"] is True
        assert status_data["user"]["username"] == "superadmin"

        # 3. Setup again should be forbidden
        second_setup = await client.post(
            "/api/auth/setup",
            json={"username": "hacker", "password": "password"},
        )
        assert second_setup.status_code == 403

        # 4. Logout
        logout_res = await client.post("/api/auth/logout")
        assert logout_res.status_code == 200

        # 5. Status should be initialized but unauthenticated
        unauth_status = await client.get("/api/auth/status")
        assert unauth_status.json()["authenticated"] is False

        # 6. Login with wrong password fails
        bad_login = await client.post(
            "/api/auth/login",
            json={"username": "superadmin", "password": "WrongPassword"},
        )
        assert bad_login.status_code == 401

        # 7. Login with correct password succeeds
        good_login = await client.post(
            "/api/auth/login",
            json={"username": "superadmin", "password": "SuperSecretPassword123!"},
        )
        assert good_login.status_code == 200
        assert good_login.json()["user"]["username"] == "superadmin"
        assert "atenea_session" in good_login.cookies


@pytest.mark.asyncio
async def test_admin_user_management(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Setup admin
        await client.post(
            "/api/auth/setup",
            json={"username": "admin", "password": "AdminPassword123!"},
        )

        # Admin creates regular user
        create_res = await client.post(
            "/api/auth/users",
            json={"username": "developer", "password": "DevPassword123!", "is_admin": False},
        )
        assert create_res.status_code == 200
        dev_user = create_res.json()
        assert dev_user["username"] == "developer"
        assert dev_user["is_admin"] is False

        # Admin lists users
        list_res = await client.get("/api/auth/users")
        assert list_res.status_code == 200
        users = list_res.json()
        assert len(users) == 2
        usernames = [u["username"] for u in users]
        assert "admin" in usernames
        assert "developer" in usernames

        dev_id = dev_user["id"]

        # Admin updates user (promotes to admin and deactivates)
        patch_res = await client.patch(
            f"/api/auth/users/{dev_id}",
            json={"is_admin": True, "is_active": False, "password": "NewDevPassword123!"},
        )
        assert patch_res.status_code == 200
        patched = patch_res.json()
        assert patched["is_admin"] is True
        assert patched["is_active"] is False

        # Admin cannot delete own account
        admin_user = next(u for u in users if u["username"] == "admin")
        self_del_res = await client.delete(f"/api/auth/users/{admin_user['id']}")
        assert self_del_res.status_code == 400

        # Admin deletes user (default soft delete)
        del_res = await client.delete(f"/api/auth/users/{dev_id}")
        assert del_res.status_code == 200
        assert del_res.json()["strategy"] == "soft"


@pytest.mark.asyncio
async def test_login_rate_limiting(test_app):
    from src.presentation.api.dependencies.rate_limiter import default_rate_limiter
    default_rate_limiter.reset()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Setup admin first
        await client.post(
            "/api/auth/setup",
            json={"username": "admin", "password": "AdminPassword123!"},
        )
        default_rate_limiter.reset()

        # Perform 5 failed logins (allowed limit is 5)
        for _ in range(5):
            res = await client.post(
                "/api/auth/login",
                json={"username": "admin", "password": "WrongPassword"},
            )
            assert res.status_code == 401

        # 6th attempt must trigger 429 Too Many Requests
        rate_limited_res = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "WrongPassword"},
        )
        assert rate_limited_res.status_code == 429
        assert "Retry-After" in rate_limited_res.headers
        assert rate_limited_res.json()["detail"] == "Too many requests. Please try again later."


@pytest.mark.asyncio
async def test_setup_requires_token_when_configured(auth_components, tmp_path):
    from src.presentation.api.dependencies.rate_limiter import default_rate_limiter
    default_rate_limiter.reset()

    user_repo, auth_service = auth_components
    settings = Settings(
        vault_path=str(tmp_path / "vault"),
        db_path=str(tmp_path / "auth_test.db"),
        auth_secret_key="test_auth_secret_key_32_bytes_long_entropy",
        initial_setup_token="secure_bootstrap_token_xyz",
    )
    app = create_app(settings=settings, auth_service=auth_service)
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Setup without token fails with 403
        no_token_res = await client.post(
            "/api/auth/setup",
            json={"username": "superadmin", "password": "SuperSecretPassword123!"},
        )
        assert no_token_res.status_code == 403
        assert "setup token" in no_token_res.json()["detail"].lower()

        # 2. Setup with invalid token fails with 403
        bad_token_res = await client.post(
            "/api/auth/setup",
            json={
                "username": "superadmin",
                "password": "SuperSecretPassword123!",
                "setup_token": "wrong_token",
            },
        )
        assert bad_token_res.status_code == 403

        # 3. Setup with valid token in body succeeds
        valid_res = await client.post(
            "/api/auth/setup",
            json={
                "username": "superadmin",
                "password": "SuperSecretPassword123!",
                "setup_token": "secure_bootstrap_token_xyz",
            },
        )
        assert valid_res.status_code == 200
        assert valid_res.json()["user"]["username"] == "superadmin"


@pytest.mark.asyncio
async def test_self_password_change_flow(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Setup admin
        await client.post(
            "/api/auth/setup",
            json={"username": "selfadmin", "password": "OriginalPassword123!"},
        )

        # 1. Change password with incorrect current password fails with 401
        bad_change = await client.post(
            "/api/auth/change-password",
            json={"current_password": "WrongPassword!", "new_password": "BrandNewPassword123!"},
        )
        assert bad_change.status_code == 401

        # 2. Change password with too short new password fails with 422 or 400
        short_change = await client.post(
            "/api/auth/change-password",
            json={"current_password": "OriginalPassword123!", "new_password": "short"},
        )
        assert short_change.status_code in (400, 422)

        # 3. Valid change password succeeds
        good_change = await client.post(
            "/api/auth/change-password",
            json={"current_password": "OriginalPassword123!", "new_password": "BrandNewPassword123!"},
        )
        assert good_change.status_code == 200
        assert "message" in good_change.json()

        # 4. Old password can no longer be used to login
        old_login = await client.post(
            "/api/auth/login",
            json={"username": "selfadmin", "password": "OriginalPassword123!"},
        )
        assert old_login.status_code == 401

        # 5. New password logs in successfully
        new_login = await client.post(
            "/api/auth/login",
            json={"username": "selfadmin", "password": "BrandNewPassword123!"},
        )
        assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_non_admin_cannot_access_user_management(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Setup admin
        await client.post(
            "/api/auth/setup",
            json={"username": "rootadmin", "password": "RootAdminPassword123!"},
        )
        # Admin creates normal user
        await client.post(
            "/api/auth/users",
            json={"username": "plainuser", "password": "PlainUserPassword123!", "is_admin": False},
        )

        # Login as normal user
        await client.post(
            "/api/auth/login",
            json={"username": "plainuser", "password": "PlainUserPassword123!"},
        )

        # Normal user cannot list users (403)
        res_list = await client.get("/api/auth/users")
        assert res_list.status_code == 403

        # Normal user cannot create users (403)
        res_create = await client.post(
            "/api/auth/users",
            json={"username": "other", "password": "OtherPassword123!"},
        )
        assert res_create.status_code == 403




