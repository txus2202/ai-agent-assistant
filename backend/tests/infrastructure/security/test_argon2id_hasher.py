import pytest
from src.infrastructure.security.argon2_hasher import Argon2idPasswordHasher


def test_argon2id_hash_and_verify_success():
    hasher = Argon2idPasswordHasher()
    hashed = hasher.hash("MiContraseñaSecreta123!")

    assert hashed.startswith("$argon2id$")
    assert hasher.verify("MiContraseñaSecreta123!", hashed) is True


def test_argon2id_verify_fails_with_wrong_password():
    hasher = Argon2idPasswordHasher()
    hashed = hasher.hash("CorrectPassword")

    assert hasher.verify("WrongPassword", hashed) is False


def test_argon2id_verify_handles_corrupt_hash_gracefully():
    hasher = Argon2idPasswordHasher()
    assert hasher.verify("AnyPassword", "corrupt_invalid_hash") is False
    assert hasher.verify("AnyPassword", "") is False


def test_argon2id_produces_unique_salts():
    hasher = Argon2idPasswordHasher()
    hash1 = hasher.hash("SamePassword")
    hash2 = hasher.hash("SamePassword")

    assert hash1 != hash2
    assert hasher.verify("SamePassword", hash1) is True
    assert hasher.verify("SamePassword", hash2) is True


def test_argon2id_rejects_empty_null_byte_or_overlong_passwords():
    hasher = Argon2idPasswordHasher()
    with pytest.raises(ValueError, match="empty or contain null bytes"):
        hasher.hash("")
    with pytest.raises(ValueError, match="empty or contain null bytes"):
        hasher.hash("bad\x00password")
    with pytest.raises(ValueError, match="cannot exceed 128 characters"):
        hasher.hash("A" * 129)

    valid_hash = hasher.hash("ValidPass123!")
    assert hasher.verify("bad\x00password", valid_hash) is False
    assert hasher.verify("A" * 129, valid_hash) is False


