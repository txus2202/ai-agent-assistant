from datetime import datetime, timezone, timedelta
from typing import Any, Optional
import uuid
import jwt
from src.domain.ports.token_service import ITokenService

INSECURE_DEFAULT_SECRETS = frozenset({
    "atenea_super_secret_auth_key_must_be_overridden_in_production_32_bytes",
    "change_this_to_a_secure_random_key_at_least_32_bytes_long",
})

DEFAULT_ISSUER = "atenea"
DEFAULT_AUDIENCE = "atenea-web"


class JwtTokenService(ITokenService):
    """
    JWT token service using PyJWT and HMAC-SHA256 with fail-fast key validation.
    """

    def __init__(
        self,
        secret_key: str,
        default_expiry_seconds: int = 28800,
        algorithm: str = "HS256",
        issuer: str = DEFAULT_ISSUER,
        audience: str = DEFAULT_AUDIENCE,
    ) -> None:
        if not secret_key or len(secret_key) < 32:
            raise ValueError("JWT secret_key must be at least 32 characters long.")
        if secret_key in INSECURE_DEFAULT_SECRETS:
            raise ValueError(
                "Insecure default secret key detected. You must set a unique, cryptographically strong AUTH_SECRET_KEY."
            )

        self._secret_key = secret_key
        self._default_expiry_seconds = default_expiry_seconds
        self._algorithm = algorithm
        self._issuer = issuer
        self._audience = audience

    def create_access_token(
        self,
        user_id: str,
        username: str,
        is_admin: bool = False,
        expires_in_seconds: Optional[int] = None,
        token_version: int = 1,
    ) -> str:
        now = datetime.now(timezone.utc)
        duration = expires_in_seconds if expires_in_seconds is not None else self._default_expiry_seconds
        exp = now + timedelta(seconds=duration)

        payload = {
            "sub": user_id,
            "preferred_username": username,
            "is_admin": is_admin,
            "token_version": token_version,
            "iss": self._issuer,
            "aud": self._audience,
            "jti": str(uuid.uuid4()),
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp()),
        }
        return jwt.encode(payload, self._secret_key, algorithm=self._algorithm)

    def decode_and_validate_token(self, token: str) -> Optional[dict[str, Any]]:
        try:
            return jwt.decode(
                token,
                self._secret_key,
                algorithms=[self._algorithm],
                issuer=self._issuer,
                audience=self._audience,
            )
        except (jwt.PyJWTError, ValueError):
            return None
