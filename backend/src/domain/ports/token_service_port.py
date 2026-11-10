from abc import abstractmethod
from typing import Any, Optional, Protocol, runtime_checkable


@runtime_checkable
class ITokenService(Protocol):
    """Port for issuing and verifying authentication tokens."""

    @abstractmethod
    def create_access_token(
        self,
        user_id: str,
        username: str,
        is_admin: bool = False,
        expires_in_seconds: Optional[int] = None,
        token_version: int = 1,
    ) -> str:
        """Create signed access token (JWT)."""

    @abstractmethod
    def decode_and_validate_token(self, token: str) -> Optional[dict[str, Any]]:
        """Decode and validate access token, returning payload claims or None if invalid/expired."""

