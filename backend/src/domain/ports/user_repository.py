"""
Domain Port: IUserRepository
"""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from src.domain.entities.user import User


@runtime_checkable
class IUserRepository(Protocol):
    """Port for user persistence."""

    async def get_by_id(self, user_id: str) -> Optional[User]:
        """Fetch user by unique ID."""
        ...

    async def get_by_username(self, username: str) -> Optional[User]:
        """Fetch user by username (case-insensitive)."""
        ...

    async def save(self, user: User) -> None:
        """Create or update user."""
        ...

    async def count_users(self) -> int:
        """Return total number of registered users."""
        ...

    async def list_users(self) -> list[User]:
        """Return list of all registered users."""
        ...

    async def delete(self, user_id: str) -> None:
        """Permanently delete user by ID."""
        ...

