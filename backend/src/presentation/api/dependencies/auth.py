from typing import Optional
from fastapi import Depends, HTTPException, Request, WebSocket, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from src.application.services.auth_service import AuthService
from src.domain.entities.user import User
from src.domain.ports.agent_config_repository import IAgentConfigRepository
from src.domain.ports.debate_repository import IDebateRepository
from src.domain.ports.user_repository import IUserRepository
from src.infrastructure.persistence.sqlite_agent_config_repository import SqliteAgentConfigRepository
from src.infrastructure.persistence.sqlite_debate_repository import SqliteDebateRepository
from src.infrastructure.persistence.sqlite_user_repository import SQLiteUserRepository
from src.infrastructure.persistence.postgres_user_repository import PostgreSQLUserRepository
from src.infrastructure.security.argon2_hasher import Argon2idPasswordHasher
from src.infrastructure.security.jwt_token_service import JwtTokenService
from src.presentation.api.config import Settings, get_settings
from src.presentation.api.dependencies.agents import build_agent_catalog_repository

from starlette.requests import HTTPConnection

security_bearer = HTTPBearer(auto_error=False)

_auth_service_instance: Optional[AuthService] = None


def get_debate_repository(settings: Settings = Depends(get_settings)) -> IDebateRepository:
    """Centralized dependency provider for IDebateRepository."""
    return SqliteDebateRepository(db_path=str(settings.sqlite_db_path))


def get_agent_config_repository(settings: Settings = Depends(get_settings)) -> IAgentConfigRepository:
    """Centralized dependency provider for IAgentConfigRepository."""
    return SqliteAgentConfigRepository(
        db_path=str(settings.sqlite_db_path),
        agent_catalog=build_agent_catalog_repository(settings),
    )


def get_auth_service(connection: HTTPConnection) -> AuthService:
    """Returns AuthService singleton or request/connection state override."""
    app_state = getattr(connection.app, "state", None)
    if app_state and hasattr(app_state, "auth_service") and app_state.auth_service:
        return app_state.auth_service

    global _auth_service_instance
    if _auth_service_instance is None:
        settings = get_settings()
        db_url = getattr(settings, "database_url", "")
        user_repo: IUserRepository
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


def _extract_candidate_hosts(websocket: WebSocket) -> set[str]:
    candidate_hosts: set[str] = set()
    for header_name in ("x-forwarded-host", "host"):
        header_val = websocket.headers.get(header_name)
        if not header_val:
            continue
        for item in header_val.split(","):
            h = item.strip().lower()
            if h:
                candidate_hosts.add(h)
                candidate_hosts.add(h.split(":")[0])
    return candidate_hosts


def _matches_cors_pattern(pattern: str, origin_scheme: str, origin_host: str) -> bool:
    if pattern.startswith("*.") and origin_host.endswith(pattern[1:]):
        return True
    if "://" not in pattern:
        return False
    from urllib.parse import urlparse
    pat_parsed = urlparse(pattern)
    if pat_parsed.scheme != origin_scheme:
        return False
    pat_host = (pat_parsed.hostname or "").lower()
    return bool(pat_host.startswith("*.") and origin_host.endswith(pat_host[1:]))


def _is_same_tailnet(origin_host: str, candidate_hosts: set[str]) -> bool:
    for h in candidate_hosts:
        if not h.endswith(".ts.net"):
            continue
        parts = h.split(".")
        if len(parts) >= 4:
            tailnet_suffix = "." + ".".join(parts[-3:])
            if origin_host.endswith(tailnet_suffix):
                return True
    return False


def validate_websocket_origin(websocket: WebSocket, settings: Settings) -> bool:
    """
    Validates origin header against CORS settings for CSWSH defense.
    Allows:
    1. Requests without an Origin header (non-browser clients, local tools).
    2. Wildcard '*' in cors_origins.
    3. Explicit origin matches in cors_origins.
    4. Same-origin requests: when origin hostname matches Host or X-Forwarded-Host header.
    5. Pattern matching in cors_origins (e.g. *.ts.net, https://*.ts.net, *.local).
    6. Automatically allows Tailscale domains (*.ts.net) when accessing over Tailscale.
    """
    origin = websocket.headers.get("origin")
    if not origin or "*" in settings.cors_origins:
        return True

    clean_origin = origin.strip().lower()

    # 2. Direct match against cors_origins
    cors_set = {o.strip().lower() for o in settings.cors_origins}
    if clean_origin in cors_set:
        return True

    from urllib.parse import urlparse
    origin_parsed = urlparse(clean_origin)
    origin_host = (origin_parsed.hostname or "").lower()

    # 3. Same-origin verification (Origin matches Host or X-Forwarded-Host)
    candidate_hosts = _extract_candidate_hosts(websocket)
    if (origin_host and origin_host in candidate_hosts) or origin_parsed.netloc.lower() in candidate_hosts:
        return True

    # 4. Pattern matching in cors_origins (e.g. *.ts.net, https://*.ts.net, *.local)
    if any(_matches_cors_pattern(pattern, origin_parsed.scheme, origin_host) for pattern in cors_set):
        return True

    # 5. Intra-tailnet verification: allow nodes only within the exact same tailnet (e.g. *.taild9f14f.ts.net)
    return _is_same_tailnet(origin_host, candidate_hosts)


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


def get_security_notifier(connection: HTTPConnection) -> "ISecurityNotifier":
    """Dependency providing ISecurityNotifier from app.state or initialized from settings."""
    from src.domain.ports.security_notifier import ISecurityNotifier
    from src.infrastructure.security.telegram_notifier import TelegramSecurityNotifier

    app_state = getattr(connection.app, "state", None)
    if app_state and hasattr(app_state, "security_notifier") and app_state.security_notifier is not None:
        notifier: ISecurityNotifier = app_state.security_notifier
        return notifier

    settings = (app_state.settings if app_state and hasattr(app_state, "settings") else None) or get_settings()
    return TelegramSecurityNotifier(
        bot_token=settings.telegram_bot_token,
        chat_id=settings.telegram_chat_id,
        enabled=settings.telegram_alerts_enabled,
        alert_on_login_success=settings.telegram_alert_on_login_success,
        alert_admin_only_success=settings.telegram_alert_admin_only_success,
        alert_on_login_failure=settings.telegram_alert_on_login_failure,
        failed_login_threshold=settings.telegram_alert_failed_login_threshold,
        alert_on_rate_limit=settings.telegram_alert_on_rate_limit,
        throttle_seconds=settings.telegram_alert_throttle_seconds,
    )


