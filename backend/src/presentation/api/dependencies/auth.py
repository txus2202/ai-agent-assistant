from typing import Optional
from fastapi import Depends, HTTPException, Request, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from src.application.services.auth_service import AuthService
from src.domain.entities.user import User
from src.domain.ports.agent_config_repository import IAgentConfigRepository
from src.domain.ports.debate_repository import IDebateRepository
from src.infrastructure.persistence.sqlite_agent_config_repository import SqliteAgentConfigRepository
from src.infrastructure.persistence.sqlite_debate_repository import SqliteDebateRepository
from src.infrastructure.persistence.sqlite_user_repository import SQLiteUserRepository
from src.infrastructure.persistence.postgres_user_repository import PostgreSQLUserRepository
from src.infrastructure.security.argon2_hasher import Argon2idPasswordHasher
from src.infrastructure.security.jwt_token_service import JwtTokenService
from src.presentation.api.config import Settings, get_settings

from starlette.requests import HTTPConnection

security_bearer = HTTPBearer(auto_error=False)

_auth_service_instance: Optional[AuthService] = None


def get_debate_repository(settings: Settings = Depends(get_settings)) -> IDebateRepository:
    """Centralized dependency provider for IDebateRepository."""
    return SqliteDebateRepository(db_path=str(settings.sqlite_db_path))


def get_agent_config_repository(settings: Settings = Depends(get_settings)) -> IAgentConfigRepository:
    """Centralized dependency provider for IAgentConfigRepository."""
    return SqliteAgentConfigRepository(db_path=str(settings.sqlite_db_path))


def get_auth_service(connection: HTTPConnection) -> AuthService:
    """Returns AuthService singleton or request/connection state override."""
    app_state = getattr(connection.app, "state", None)
    if app_state and hasattr(app_state, "auth_service") and app_state.auth_service:
        return app_state.auth_service

    global _auth_service_instance
    if _auth_service_instance is None:
        settings = get_settings()
        db_url = getattr(settings, "database_url", "")
        if db_url and db_url.startswith(("postgres://", "postgresql://")):
            # PostgreSQL pool injected from lifespan
            pg_pool = getattr(app_state, "db_pool", None)
            if pg_pool:
                user_repo = PostgreSQLUserRepository(pool=pg_pool)
            else:
                raise RuntimeError(
                    "DATABASE_URL is configured for PostgreSQL, but no database pool was initialized in app.state.db_pool. "
                    "Check lifespan startup logs or asyncpg driver installation."
                )
        else:
            user_repo = SQLiteUserRepository(db_path=str(settings.sqlite_db_path))

        hasher = Argon2idPasswordHasher()
        token_svc = JwtTokenService(
            secret_key=settings.auth_secret_key,
            default_expiry_seconds=settings.auth_token_expiry_seconds,
        )

        _auth_service_instance = AuthService(
            user_repo=user_repo,
            hasher=hasher,
            token_service=token_svc,
            delete_strategy=settings.auth_delete_strategy,
            debate_repo=get_debate_repository(settings),
            agent_config_repo=get_agent_config_repository(settings),
        )
    return _auth_service_instance


def reset_auth_service() -> None:
    global _auth_service_instance
    _auth_service_instance = None


def validate_websocket_origin(websocket: WebSocket, settings: Settings) -> bool:
    """Validates origin header against CORS settings for CSWSH defense."""
    origin = websocket.headers.get("origin")
    if origin and "*" not in settings.cors_origins:
        if origin not in set(settings.cors_origins):
            return False
    return True


async def authenticate_websocket(
    websocket: WebSocket,
    auth_service: AuthService,
    settings: Settings,
) -> Optional[User]:
    """
    Validates WebSocket authentication strictly (Fail-Closed).
    Returns authenticated User if valid, or closes connection with 1008 and returns None.
    Rejects connection if system is uninitialized or token is invalid.
    """
    if not await auth_service.is_initialized():
        await websocket.close(code=1008, reason="System setup not completed")
        return None

    # 1. Check HttpOnly cookie
    token = websocket.cookies.get(settings.auth_cookie_name)

    # 2. Check Authorization Bearer header
    if not token and "authorization" in websocket.headers:
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()

    # 3. Fallback to query parameter (for non-browser clients)
    if not token:
        token = websocket.query_params.get("token")

    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return None

    user = await auth_service.validate_token(token)
    if not user or not user.is_active:
        await websocket.close(code=1008, reason="Unauthorized")
        return None

    return user


async def get_current_user_optional(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
) -> Optional[User]:
    """
    Extracts user from cookie 'atenea_session' or Authorization header Bearer token.
    Returns None if not authenticated.
    """
    token = None
    settings = get_settings()

    # 1. Check Bearer token in header
    if bearer and bearer.credentials:
        token = bearer.credentials

    # 2. Check Cookie
    if not token and settings.auth_cookie_name in request.cookies:
        token = request.cookies[settings.auth_cookie_name]

    if not token:
        return None

    return await auth_service.validate_token(token)


def get_current_user(
    user: Optional[User] = Depends(get_current_user_optional),
) -> User:
    """
    Requires authentication. Raises 401 if not authenticated.
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


def require_admin(
    user: User = Depends(get_current_user),
) -> User:
    """
    Requires user to have admin privileges. Raises 403 if not admin.
    """
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )
    return user

