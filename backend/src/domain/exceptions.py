"""
Domain exceptions.

All domain-level exceptions are defined here. Infrastructure adapters must
catch their SDK/storage-specific exceptions and re-raise them as one of
these types to preserve the anti-corruption layer (ADR-004).
"""
from __future__ import annotations

import uuid


class LLMProviderError(Exception):
    """Raised when any LLM provider call fails (network, quota, invalid key, etc.)."""


class AgentNotFoundError(Exception):
    """Raised by use cases when an Agent with the given ID does not exist."""

    def __init__(self, agent_id: uuid.UUID) -> None:
        super().__init__(f"Agent not found: {agent_id}")
        self.agent_id = agent_id


class RepositoryError(Exception):
    """Raised when a repository adapter encounters a storage-level failure."""


class ProviderNotRegisteredError(Exception):
    """
    Raised when an Agent's provider has no adapter registered in the
    LLM provider registry.

    This is a configuration error, not a validation error — the prompt and
    agent are valid, but the runtime registry is incomplete.
    """

    def __init__(self, provider: str, available: list[str]) -> None:
        super().__init__(
            f"No LLM provider registered for '{provider}'. "
            f"Available providers: {available}."
        )
        self.provider = provider
        self.available = available


class ExtractionError(Exception):
    """
    Raised when a source extractor (PDF, URL, Image) fails to extract text.

    Infrastructure adapters (PDFExtractor, URLExtractor) must catch their
    internal exceptions (PyMuPDF errors, httpx errors, etc.) and re-raise
    them as ExtractionError to preserve the anti-corruption layer (ADR-004).
    """


class AuthenticationError(Exception):
    """Base exception for authentication errors."""


class AuthorizationError(Exception):
    """Base exception for authorization and access control errors."""


class DomainValidationError(Exception):
    """Base exception for domain business validation errors."""


class WeakPasswordError(DomainValidationError):
    """Raised when a password does not meet minimum strength requirements."""


class SelfModificationError(AuthorizationError):
    """Raised when an administrator attempts prohibited self-modification (e.g. self-delete or self-deactivation)."""


class InvalidCredentialsError(AuthenticationError):
    """Raised when provided credentials (username/password) are incorrect."""


class UserInactiveError(AuthenticationError):
    """Raised when the user account is deactivated."""


class SetupAlreadyCompletedError(AuthenticationError):
    """Raised when initial setup is attempted after users already exist."""


class UserAlreadyExistsError(AuthenticationError):
    """Raised when attempting to create a user with a duplicate username."""


class UserNotFoundError(AuthenticationError):
    """Raised when a user is not found."""


class UnauthorizedError(AuthorizationError):
    """Raised when a user attempts an action without sufficient permissions."""


class LastAdminError(AuthorizationError):
    """Raised when an operation would leave the system without an active administrator."""




class InvalidTokenError(AuthenticationError):
    """Raised when a session token is invalid or malformed."""


class TokenExpiredError(AuthenticationError):
    """Raised when a session token has expired."""
