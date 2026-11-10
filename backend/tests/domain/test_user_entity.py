from datetime import datetime, timezone
import pytest
from src.domain.entities.user import User


def test_user_creation_with_minimal_fields():
    user = User(
        id="usr-123",
        username="admin",
        password_hash="$argon2id$v=19$m=65536,t=2,p=2$mockhash",
    )
    assert user.id == "usr-123"
    assert user.username == "admin"
    assert user.password_hash == "$argon2id$v=19$m=65536,t=2,p=2$mockhash"
    assert user.is_admin is False
    assert user.is_active is True
    assert isinstance(user.created_at, datetime)


def test_user_creation_with_admin_and_active_flags():
    now = datetime.now(timezone.utc)
    user = User(
        id="usr-456",
        username="supervisor",
        password_hash="hash456",
        is_admin=True,
        is_active=False,
        created_at=now,
    )
    assert user.is_admin is True
    assert user.is_active is False
    assert user.created_at == now


def test_user_entity_is_immutable():
    user = User(
        id="usr-123",
        username="admin",
        password_hash="hash",
    )
    with pytest.raises(Exception):
        user.username = "hacked"  # type: ignore[misc]


def test_user_username_normalization():
    user = User(
        id="usr-789",
        username="  Admin_User  ",
        password_hash="hash",
    )
    assert user.username == "admin_user"
    assert user.token_version == 1
    assert user.deleted_at is None


def test_user_username_validation_rejects_invalid():
    with pytest.raises(ValueError):
        User(id="1", username="ab", password_hash="h")  # too short

    with pytest.raises(ValueError):
        User(id="1", username="a" * 51, password_hash="h")  # too long

    with pytest.raises(ValueError):
        User(id="1", username="bad user with spaces", password_hash="h")

    with pytest.raises(ValueError):
        User(id="1", username="invalid!@#$", password_hash="h")


