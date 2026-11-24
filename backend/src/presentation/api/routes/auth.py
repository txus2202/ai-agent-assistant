import asyncio
import secrets
from datetime import datetime
from typing import Any, Coroutine, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from src.application.services.auth_service import AuthService
from src.domain.entities.user import User
from src.domain.exceptions import (
    InvalidCredentialsError,
    SetupAlreadyCompletedError,
    UserAlreadyExistsError,
    UserInactiveError,
    UserNotFoundError,
    LastAdminError,
    SelfModificationError,
    WeakPasswordError,
)
from src.domain.ports.security_notifier import ISecurityNotifier
from src.presentation.api.config import get_settings
from src.presentation.api.dependencies.auth import (
    get_auth_service,
    get_current_user,
    get_current_user_optional,
    get_security_notifier,
    require_admin,
)
from src.presentation.api.dependencies.rate_limiter import (
    default_rate_limiter,
    enforce_rate_limit,
    get_client_country,
    get_client_ip,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

_background_tasks: set[asyncio.Task[Any]] = set()


def fire_and_forget(coro: Coroutine[Any, Any, Any]) -> Optional[asyncio.Task[Any]]:
    """Execute background async task without blocking request lifecycle while preventing GC."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        coro.close()
        return None
    task = loop.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


async def check_login_rate_limit(request: Request) -> None:
    settings = getattr(request.app.state, "settings", None) or get_settings()
    limiter = getattr(request.app.state, "rate_limiter", default_rate_limiter)
    trust_x_forwarded_for = getattr(settings, "auth_trust_x_forwarded_for", False)
    try:
        enforce_rate_limit(
            request=request,
            max_requests=settings.auth_rate_limit_login_attempts,
            window_seconds=settings.auth_rate_limit_login_window_seconds,
            limiter=limiter,
            key_prefix="auth:login",
            trust_x_forwarded_for=trust_x_forwarded_for,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            notifier = get_security_notifier(request)
            client_ip = get_client_ip(request, trust_x_forwarded_for=trust_x_forwarded_for)
            country = get_client_country(request, trust_x_forwarded_for=trust_x_forwarded_for)
            user_agent = request.headers.get("user-agent")
            fire_and_forget(
                notifier.notify_rate_limit(
                    client_ip=client_ip,
                    endpoint="/api/auth/login",
                    user_agent=user_agent,
                    country=country,
                )
            )
            await asyncio.sleep(0)
        raise exc


async def check_setup_rate_limit(request: Request) -> None:
    settings = getattr(request.app.state, "settings", None) or get_settings()
    limiter = getattr(request.app.state, "rate_limiter", default_rate_limiter)
    trust_x_forwarded_for = getattr(settings, "auth_trust_x_forwarded_for", False)
    try:
        enforce_rate_limit(
            request=request,
            max_requests=settings.auth_rate_limit_setup_attempts,
            window_seconds=settings.auth_rate_limit_setup_window_seconds,
            limiter=limiter,
            key_prefix="auth:setup",
            trust_x_forwarded_for=trust_x_forwarded_for,
        )
    except HTTPException as exc:
        if exc.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            notifier = get_security_notifier(request)
            client_ip = get_client_ip(request, trust_x_forwarded_for=trust_x_forwarded_for)
            country = get_client_country(request, trust_x_forwarded_for=trust_x_forwarded_for)
            user_agent = request.headers.get("user-agent")
            fire_and_forget(
                notifier.notify_rate_limit(
                    client_ip=client_ip,
                    endpoint="/api/auth/setup",
                    user_agent=user_agent,
                    country=country,
                )
            )
            await asyncio.sleep(0)
        raise exc


class UserPublic(BaseModel):
    id: str
    username: str
    is_admin: bool
    is_active: bool
    created_at: datetime
    deleted_at: Optional[datetime] = None


class AuthStatusResponse(BaseModel):
    initialized: bool
    authenticated: bool
    setup_token_required: bool = False
    user: Optional[UserPublic] = None


class CredentialsRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)


class SetupRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    setup_token: Optional[str] = None


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    is_admin: bool = False


class UpdateUserRequest(BaseModel):
    is_admin: Optional[bool] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)


class DeleteUserResponse(BaseModel):
    message: str
    strategy: str



class AuthSuccessResponse(BaseModel):
    user: UserPublic
    message: str


def _user_to_public(user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        username=user.username,
        is_admin=user.is_admin,
        is_active=user.is_active,
        created_at=user.created_at,
        deleted_at=user.deleted_at,
    )


def _set_auth_cookie(response: Response, token: str, request: Optional[Request] = None) -> None:
    settings = (getattr(request.app.state, "settings", None) if request else None) or get_settings()
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        samesite=settings.auth_cookie_samesite,  # type: ignore[arg-type]
        secure=settings.auth_cookie_secure,
        max_age=settings.auth_token_expiry_seconds,
        path="/",
    )


@router.get("/status")
async def get_status(
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    current_user: Optional[User] = Depends(get_current_user_optional),
) -> AuthStatusResponse:
    settings = getattr(request.app.state, "settings", None) or get_settings()
    initialized = await auth_service.is_initialized()
    return AuthStatusResponse(
        initialized=initialized,
        authenticated=current_user is not None,
        setup_token_required=bool(settings.initial_setup_token) and not initialized,
        user=_user_to_public(current_user) if current_user else None,
    )


@router.post(
    "/setup",
    dependencies=[Depends(check_setup_rate_limit)],
    responses={
        403: {"description": "Setup has already been completed or invalid setup token"},
        429: {"description": "Too many setup attempts"},
    },
)
async def initial_setup(
    body: SetupRequest,
    response: Response,
    request: Request,
    x_setup_token: Optional[str] = Header(default=None, alias="X-Setup-Token"),
    auth_service: AuthService = Depends(get_auth_service),
    notifier: ISecurityNotifier = Depends(get_security_notifier),
) -> AuthSuccessResponse:
    settings = getattr(request.app.state, "settings", None) or get_settings()
    trust_x_forwarded_for = getattr(settings, "auth_trust_x_forwarded_for", False)
    client_ip = get_client_ip(request, trust_x_forwarded_for=trust_x_forwarded_for)
    country = get_client_country(request, trust_x_forwarded_for=trust_x_forwarded_for)
    user_agent = request.headers.get("user-agent")

    if settings.initial_setup_token:
        provided_token = body.setup_token or x_setup_token or ""
        if not secrets.compare_digest(provided_token, settings.initial_setup_token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Setup requires a valid setup token configured in INITIAL_SETUP_TOKEN",
            )
    try:
        token, user = await auth_service.setup_initial_admin(
            username=body.username,
            password=body.password,
        )
        _set_auth_cookie(response, token, request=request)
        fire_and_forget(
            notifier.notify_login_attempt(
                username=user.username,
                client_ip=client_ip,
                success=True,
                is_admin=True,
                user_agent=user_agent,
                country=country,
                reason="Inicialización de administrador",
            )
        )
        return AuthSuccessResponse(
            user=_user_to_public(user),
            message="Administrator account initialized successfully",
        )
    except SetupAlreadyCompletedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post(
    "/login",
    dependencies=[Depends(check_login_rate_limit)],
    responses={
        401: {"description": "Invalid username or password"},
        403: {"description": "User account inactive"},
        429: {"description": "Too many login attempts"},
    },
)
async def login(
    body: CredentialsRequest,
    response: Response,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
    notifier: ISecurityNotifier = Depends(get_security_notifier),
) -> AuthSuccessResponse:
    settings = getattr(request.app.state, "settings", None) or get_settings()
    trust_x_forwarded_for = getattr(settings, "auth_trust_x_forwarded_for", False)
    client_ip = get_client_ip(request, trust_x_forwarded_for=trust_x_forwarded_for)
    country = get_client_country(request, trust_x_forwarded_for=trust_x_forwarded_for)
    user_agent = request.headers.get("user-agent")

    try:
        token, user = await auth_service.authenticate(
            username=body.username,
            password=body.password,
        )
        limiter = getattr(request.app.state, "rate_limiter", default_rate_limiter)
        limiter.reset_key(f"auth:login:{client_ip}")
        _set_auth_cookie(response, token, request=request)
        fire_and_forget(
            notifier.notify_login_attempt(
                username=user.username,
                client_ip=client_ip,
                success=True,
                is_admin=user.is_admin,
                user_agent=user_agent,
                country=country,
            )
        )
        return AuthSuccessResponse(
            user=_user_to_public(user),
            message="Authenticated successfully",
        )
    except InvalidCredentialsError as exc:
        metrics = getattr(request.app.state, "metrics_service", None)
        if metrics:
            metrics.inc_auth_failed_login(reason="invalid_credentials")
        fire_and_forget(
            notifier.notify_login_attempt(
                username=body.username,
                client_ip=client_ip,
                success=False,
                user_agent=user_agent,
                country=country,
                reason="Credenciales inválidas",
            )
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    except UserInactiveError as exc:
        metrics = getattr(request.app.state, "metrics_service", None)
        if metrics:
            metrics.inc_auth_failed_login(reason="user_inactive")
        fire_and_forget(
            notifier.notify_login_attempt(
                username=body.username,
                client_ip=client_ip,
                success=False,
                user_agent=user_agent,
                country=country,
                reason="Cuenta desactivada",
            )
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc


@router.post("/logout")
async def logout(response: Response, request: Request) -> dict[str, str]:
    settings = getattr(request.app.state, "settings", None) or get_settings()
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        httponly=True,
        samesite=settings.auth_cookie_samesite,  # type: ignore[arg-type]
        secure=settings.auth_cookie_secure,
    )
    return {"message": "Logged out successfully"}


@router.post(
    "/change-password",
    responses={
        400: {"description": "Weak password"},
        401: {"description": "Current password incorrect or session invalid"},
    },
)
async def change_password(
    body: ChangePasswordRequest,
    response: Response,
    request: Request,
    current_user: User = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    try:
        new_token, _ = await auth_service.change_password(
            user_id=current_user.id,
            current_password=body.current_password,
            new_password=body.new_password,
        )
        _set_auth_cookie(response, new_token, request=request)
        return {"message": "Password updated successfully"}
    except WeakPasswordError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserPublic:
    return _user_to_public(current_user)


@router.get("/users")
async def list_users(
    admin: User = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
) -> list[UserPublic]:
    users = await auth_service.list_users(actor=admin)
    return [_user_to_public(u) for u in users]


@router.post(
    "/users",
    responses={
        400: {"description": "Invalid input or weak password"},
        403: {"description": "Admin privileges required"},
        409: {"description": "User already exists"},
    },
)
async def create_user(
    body: CreateUserRequest,
    admin: User = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserPublic:
    try:
        new_user = await auth_service.create_user(
            actor=admin,
            username=body.username,
            password=body.password,
            is_admin=body.is_admin,
        )
        return _user_to_public(new_user)
    except UserAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except (WeakPasswordError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.patch(
    "/users/{user_id}",
    responses={
        400: {"description": "Invalid input or self-deactivation/demotion"},
        403: {"description": "Admin privileges required"},
        404: {"description": "User not found"},
        409: {"description": "Cannot demote or deactivate the last administrator"},
    },
)
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    admin: User = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserPublic:
    try:
        updated = await auth_service.update_user(
            actor=admin,
            user_id=user_id,
            is_admin=body.is_admin,
            is_active=body.is_active,
            password=body.password,
        )
        return _user_to_public(updated)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except LastAdminError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except (SelfModificationError, WeakPasswordError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.delete(
    "/users/{user_id}",
    responses={
        400: {"description": "Cannot delete own account"},
        403: {"description": "Admin privileges required"},
        404: {"description": "User not found"},
        409: {"description": "Cannot delete the last administrator"},
    },
)
async def delete_user(
    user_id: str,
    admin: User = Depends(require_admin),
    auth_service: AuthService = Depends(get_auth_service),
) -> DeleteUserResponse:
    try:
        strategy = await auth_service.delete_user(actor=admin, user_id=user_id)
        action_msg = "deactivated (soft delete)" if strategy == "soft" else "permanently deleted (hard delete)"
        return DeleteUserResponse(
            message=f"User successfully {action_msg}",
            strategy=strategy,
        )
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except LastAdminError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except (SelfModificationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


