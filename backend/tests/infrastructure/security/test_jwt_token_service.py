import time
import pytest
from src.infrastructure.security.jwt_token_service import JwtTokenService, INSECURE_DEFAULT_SECRETS


def test_jwt_rejects_short_or_insecure_default_secret_keys():
    with pytest.raises(ValueError, match="at least 32 characters"):
        JwtTokenService(secret_key="too_short_key")

    for insecure_key in INSECURE_DEFAULT_SECRETS:
        with pytest.raises(ValueError, match="Insecure default secret key"):
            JwtTokenService(secret_key=insecure_key)


def test_jwt_create_and_decode_valid_token():
    service = JwtTokenService(secret_key="my_super_secret_test_key_at_least_32_bytes_long", default_expiry_seconds=3600)
    token = service.create_access_token(user_id="u-1", username="atenea_user", is_admin=True, token_version=2)

    payload = service.decode_and_validate_token(token)
    assert payload is not None
    assert payload["sub"] == "u-1"
    assert payload["preferred_username"] == "atenea_user"
    assert payload["is_admin"] is True
    assert payload["token_version"] == 2
    assert payload["iss"] == "atenea"
    assert payload["aud"] == "atenea-web"
    assert "jti" in payload
    assert "exp" in payload
    assert "iat" in payload


def test_jwt_decode_expired_token_returns_none():
    service = JwtTokenService(secret_key="my_super_secret_test_key_at_least_32_bytes_long", default_expiry_seconds=1)
    # Expires in -10 seconds
    token = service.create_access_token(user_id="u-1", username="expired_user", expires_in_seconds=-10)

    payload = service.decode_and_validate_token(token)
    assert payload is None


def test_jwt_decode_tampered_token_returns_none():
    service = JwtTokenService(secret_key="key_one_32_bytes_long_secret_text_value", default_expiry_seconds=3600)
    token = service.create_access_token(user_id="u-1", username="user1")

    # Try decoding with different key
    other_service = JwtTokenService(secret_key="different_key_32_bytes_long_secret_value", default_expiry_seconds=3600)
    assert other_service.decode_and_validate_token(token) is None

    # Try decoding manipulated token
    tampered = token[:-4] + "abcd"
    assert service.decode_and_validate_token(tampered) is None
    assert service.decode_and_validate_token("invalid.jwt.string") is None


