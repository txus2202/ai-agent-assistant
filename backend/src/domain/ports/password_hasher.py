"""
Domain Port: IPasswordHasher
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class IPasswordHasher(Protocol):
    """Port for secure password hashing and verification."""

    def hash(self, plain_password: str) -> str:
        """Hash a plain text password with a secure salt."""
        ...

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        """Verify plain text password against a hash."""
        ...

