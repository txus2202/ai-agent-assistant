import pytest
from unittest.mock import AsyncMock, MagicMock
from src.domain.entities.user import User
from src.domain.exceptions import (
    InvalidCredentialsError,
    UserInactiveError,
    SetupAlreadyCompletedError,
    UnauthorizedError,
    LastAdminError,
    SelfModificationError,
)
from src.domain.ports.user_repository import IUserRepository
from src.domain.ports.password_hasher import IPasswordHasher
from src.domain.ports.token_service import ITokenService
from src.application.services.auth_service import AuthService


@pytest.fixture
def mock_user_repo():
    repo = MagicMock(spec=IUserRepository)
    repo.count_users = AsyncMock(return_value=0)
    repo.get_by_username = AsyncMock(return_value=None)
    repo.get_by_id = AsyncMock(return_value=None)
    repo.save = AsyncMock()
    repo.list_users = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_hasher():
    hasher = MagicMock(spec=IPasswordHasher)
    hasher.hash.side_effect = lambda pwd: f"hashed_{pwd}"
    hasher.verify.side_effect = lambda pwd, h: h == f"hashed_{pwd}"
    return hasher


@pytest.fixture
def mock_token_service():
    token_svc = MagicMock(spec=ITokenService)
    token_svc.create_access_token.return_value = "mock_jwt_token_123"
    token_svc.decode_and_validate_token.return_value = {
        "sub": "usr-1",
        "preferred_username": "admin",
        "is_admin": True,
    }
    return token_svc


@pytest.fixture
def auth_service(mock_user_repo, mock_hasher, mock_token_service):
    return AuthService(
        user_repo=mock_user_repo,
        hasher=mock_hasher,
        token_service=mock_token_service,
    )


@pytest.mark.asyncio
async def test_initial_setup_success(auth_service, mock_user_repo, mock_hasher, mock_token_service):
    mock_user_repo.count_users.return_value = 0

    token, user = await auth_service.setup_initial_admin(username="admin", password="AdminPassword123!")

    assert user.username == "admin"
    assert user.is_admin is True
    assert user.password_hash == "hashed_AdminPassword123!"
    assert token == "mock_jwt_token_123"
    mock_user_repo.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_initial_setup_fails_when_users_already_exist(auth_service, mock_user_repo):
    mock_user_repo.count_users.return_value = 1

    with pytest.raises(SetupAlreadyCompletedError):
        await auth_service.setup_initial_admin(username="admin2", password="password")


@pytest.mark.asyncio
async def test_authenticate_success(auth_service, mock_user_repo, mock_hasher):
    mock_user = User(
        id="usr-1",
        username="john",
        password_hash="hashed_secret123",
        is_admin=False,
        is_active=True,
    )
    mock_user_repo.get_by_username.return_value = mock_user

    token, user = await auth_service.authenticate(username="john", password="secret123")

    assert token == "mock_jwt_token_123"
    assert user.id == "usr-1"
    assert user.username == "john"


@pytest.mark.asyncio
async def test_authenticate_fails_with_invalid_password(auth_service, mock_user_repo):
    mock_user = User(
        id="usr-1",
        username="john",
        password_hash="hashed_secret123",
    )
    mock_user_repo.get_by_username.return_value = mock_user

    with pytest.raises(InvalidCredentialsError):
        await auth_service.authenticate(username="john", password="wrong_password")


@pytest.mark.asyncio
async def test_authenticate_fails_when_user_not_found(auth_service, mock_user_repo):
    mock_user_repo.get_by_username.return_value = None

    with pytest.raises(InvalidCredentialsError):
        await auth_service.authenticate(username="ghost", password="password")


@pytest.mark.asyncio
async def test_authenticate_fails_when_user_is_inactive(auth_service, mock_user_repo):
    mock_user = User(
        id="usr-inactive",
        username="banned",
        password_hash="hashed_pwd",
        is_active=False,
    )
    mock_user_repo.get_by_username.return_value = mock_user

    with pytest.raises(UserInactiveError):
        await auth_service.authenticate(username="banned", password="pwd")


@pytest.mark.asyncio
async def test_validate_token_success(auth_service, mock_user_repo, mock_token_service):
    mock_user = User(id="usr-1", username="admin", password_hash="h", is_admin=True)
    mock_user_repo.get_by_id.return_value = mock_user

    user = await auth_service.validate_token("valid_token")
    assert user is not None
    assert user.id == "usr-1"


@pytest.mark.asyncio
async def test_validate_token_returns_none_if_token_invalid_or_expired(auth_service, mock_token_service):
    mock_token_service.decode_and_validate_token.return_value = None

    user = await auth_service.validate_token("invalid_token")
    assert user is None


@pytest.mark.asyncio
async def test_admin_can_create_user(auth_service, mock_user_repo, mock_hasher):
    admin = User(id="admin-id", username="admin", password_hash="h", is_admin=True)

    new_user = await auth_service.create_user(
        actor=admin,
        username="newbie",
        password="NewbiePassword123!",
        is_admin=False,
    )

    assert new_user.username == "newbie"
    assert new_user.is_admin is False
    assert new_user.password_hash == "hashed_NewbiePassword123!"
    mock_user_repo.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_non_admin_cannot_create_user(auth_service):
    regular_user = User(id="u-regular", username="bob", password_hash="h", is_admin=False)

    with pytest.raises(UnauthorizedError):
        await auth_service.create_user(
            actor=regular_user,
            username="newbie",
            password="pwd",
        )


@pytest.mark.asyncio
async def test_admin_can_update_user(auth_service, mock_user_repo):
    admin = User(id="adm-1", username="admin", password_hash="h", is_admin=True)
    target = User(id="usr-2", username="bob", password_hash="old_h", is_admin=False, is_active=True)
    mock_user_repo.get_by_id.return_value = target

    updated = await auth_service.update_user(
        actor=admin,
        user_id="usr-2",
        is_admin=True,
        is_active=False,
        password="NewPassword123!",
    )

    assert updated.is_admin is True
    assert updated.is_active is False
    assert updated.password_hash == "hashed_NewPassword123!"
    mock_user_repo.save.assert_awaited_once_with(updated)


@pytest.mark.asyncio
async def test_admin_cannot_deactivate_or_demote_self(auth_service, mock_user_repo):
    admin = User(id="adm-1", username="admin", password_hash="h", is_admin=True, is_active=True)
    mock_user_repo.get_by_id.return_value = admin

    with pytest.raises(SelfModificationError, match="Cannot deactivate your own administrator account"):
        await auth_service.update_user(actor=admin, user_id="adm-1", is_active=False)

    with pytest.raises(SelfModificationError, match="Cannot revoke administrator privileges"):
        await auth_service.update_user(actor=admin, user_id="adm-1", is_admin=False)


@pytest.mark.asyncio
async def test_cannot_demote_or_deactivate_last_active_admin(auth_service, mock_user_repo):
    admin1 = User(id="adm-1", username="admin1", password_hash="h", is_admin=True, is_active=True)
    admin2 = User(id="adm-2", username="admin2", password_hash="h", is_admin=True, is_active=True)
    mock_user_repo.get_by_id.return_value = admin2
    mock_user_repo.list_users.return_value = [admin2]  # Only admin2 is active

    with pytest.raises(LastAdminError):
        await auth_service.update_user(actor=admin1, user_id="adm-2", is_admin=False)

    with pytest.raises(LastAdminError):
        await auth_service.update_user(actor=admin1, user_id="adm-2", is_active=False)


@pytest.mark.asyncio
async def test_admin_cannot_delete_self(auth_service, mock_user_repo):
    admin = User(id="adm-1", username="admin", password_hash="h", is_admin=True)
    mock_user_repo.get_by_id.return_value = admin

    with pytest.raises(SelfModificationError, match="Cannot delete your own administrator account"):
        await auth_service.delete_user(actor=admin, user_id="adm-1")


@pytest.mark.asyncio
async def test_soft_delete_user(auth_service, mock_user_repo):
    admin = User(id="adm-1", username="admin", password_hash="h", is_admin=True)
    target = User(id="usr-2", username="bob", password_hash="h", is_admin=False, is_active=True)
    mock_user_repo.get_by_id.return_value = target

    strategy = await auth_service.delete_user(actor=admin, user_id="usr-2")

    assert strategy == "soft"
    saved_user = mock_user_repo.save.await_args[0][0]
    assert saved_user.is_active is False
    assert saved_user.deleted_at is not None


@pytest.mark.asyncio
async def test_hard_delete_user_purges_debates_and_agent_configs(mock_user_repo, mock_hasher, mock_token_service):
    mock_debate_repo = MagicMock()
    mock_agent_config_repo = MagicMock()
    hard_delete_service = AuthService(
        user_repo=mock_user_repo,
        hasher=mock_hasher,
        token_service=mock_token_service,
        delete_strategy="hard",
        debate_repo=mock_debate_repo,
        agent_config_repo=mock_agent_config_repo,
    )
    admin = User(id="adm-1", username="admin", password_hash="h", is_admin=True)
    target = User(id="usr-2", username="bob", password_hash="h", is_admin=False, is_active=True)
    mock_user_repo.get_by_id.return_value = target
    mock_user_repo.delete = AsyncMock()

    strategy = await hard_delete_service.delete_user(actor=admin, user_id="usr-2")

    assert strategy == "hard"
    mock_user_repo.delete.assert_awaited_once_with("usr-2")
    mock_debate_repo.delete_by_user_id.assert_called_once_with("usr-2")
    mock_agent_config_repo.delete_by_user_id.assert_called_once_with("usr-2")


@pytest.mark.asyncio
async def test_validate_token_revoked_on_version_mismatch(auth_service, mock_user_repo, mock_token_service):
    # Token has token_version=1
    mock_token_service.decode_and_validate_token.return_value = {
        "sub": "usr-1",
        "token_version": 1,
    }
    # But user in DB had password changed and is now at token_version=2
    db_user = User(id="usr-1", username="admin", password_hash="h", is_active=True, token_version=2)
    mock_user_repo.get_by_id.return_value = db_user

    validated = await auth_service.validate_token("outdated_token")
    assert validated is None


@pytest.mark.asyncio
async def test_user_self_password_change_increments_token_version(
    auth_service, mock_user_repo, mock_hasher, mock_token_service
):
    user = User(id="usr-self", username="user1", password_hash="hashed_old_pwd", is_active=True, token_version=1)
    mock_user_repo.get_by_id.return_value = user

    new_token, updated_user = await auth_service.change_password(
        user_id="usr-self",
        current_password="old_pwd",
        new_password="NewSecretPassword123!",
    )

    assert new_token == "mock_jwt_token_123"
    assert updated_user.token_version == 2
    assert updated_user.password_hash == "hashed_NewSecretPassword123!"
    mock_user_repo.save.assert_awaited_once()
    mock_token_service.create_access_token.assert_called_once_with(
        user_id="usr-self",
        username="user1",
        is_admin=False,
        token_version=2,
    )


@pytest.mark.asyncio
async def test_reactivating_soft_deleted_user_clears_deleted_at(auth_service, mock_user_repo):
    from datetime import datetime, timezone

    admin = User(id="adm-1", username="admin", password_hash="h", is_admin=True)
    soft_deleted_target = User(
        id="usr-soft",
        username="bob",
        password_hash="h",
        is_admin=False,
        is_active=False,
        deleted_at=datetime.now(timezone.utc),
    )
    mock_user_repo.get_by_id.return_value = soft_deleted_target

    restored = await auth_service.update_user(actor=admin, user_id="usr-soft", is_active=True)

    assert restored.is_active is True
    assert restored.deleted_at is None



