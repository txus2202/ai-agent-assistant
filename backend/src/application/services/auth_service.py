import asyncio
from datetime import datetime, timezone
import logging
import uuid
from typing import Optional, Tuple
from src.domain.entities.user import User
from src.domain.exceptions import (
    InvalidCredentialsError,
    UserInactiveError,
    SetupAlreadyCompletedError,
    UnauthorizedError,
    UserNotFoundError,
    LastAdminError,
    SelfModificationError,
    WeakPasswordError,
)
from src.domain.ports.user_repository import IUserRepository
from src.domain.ports.password_hasher import IPasswordHasher
from src.domain.ports.token_service import ITokenService
from src.domain.ports.debate_repository import IDebateRepository
from src.domain.ports.agent_config_repository import IAgentConfigRepository

logger = logging.getLogger(__name__)

# Pre-computed Argon2id hash for constant-time timing attack mitigation
_DUMMY_HASH = "$argon2id$v=19$m=65536,t=2,p=2$c29tZXNhbHQxMjM0NTY3OA$9/3e3T5e0qYFmE2iU4zQ5sW8aD6gH7jK9lM1nO3pQ5s"
_WEAK_PASSWORD_MSG = "Password must be at least 8 characters long."


class AuthService:
    """
    Application service coordinating authentication, initial setup, token verification,
    self-service password changes, and user lifecycle management.
    """

    def __init__(
        self,
        user_repo: IUserRepository,
        hasher: IPasswordHasher,
        token_service: ITokenService,
        delete_strategy: str = "soft",
        debate_repo: Optional[IDebateRepository] = None,
        agent_config_repo: Optional[IAgentConfigRepository] = None,
    ) -> None:
        self._user_repo = user_repo
        self._hasher = hasher
        self._token_service = token_service
        self._delete_strategy = delete_strategy
        self._debate_repo = debate_repo
        self._agent_config_repo = agent_config_repo
        self._setup_lock = asyncio.Lock()

    async def is_initialized(self) -> bool:
        """Returns True if at least one user exists in the database."""
        count = await self._user_repo.count_users()
        return count > 0

    async def setup_initial_admin(self, username: str, password: str) -> Tuple[str, User]:
        """
        Creates the very first admin user if no users exist.
        Throws SetupAlreadyCompletedError if users already exist.
        Serialized by _setup_lock to prevent concurrent admin creation.
        """
        if len(password) < 8:
            raise WeakPasswordError(_WEAK_PASSWORD_MSG)

        async with self._setup_lock:
            if await self.is_initialized():
                raise SetupAlreadyCompletedError("Initial setup has already been completed.")

            user_id = str(uuid.uuid4())
            password_hash = await asyncio.to_thread(self._hasher.hash, password)
            user = User(
                id=user_id,
                username=username,
                password_hash=password_hash,
                is_admin=True,
                is_active=True,
                token_version=1,
            )
            await self._user_repo.save(user)

            # Assign pre-auth legacy debates to the newly created administrator
            if self._debate_repo:
                try:
                    self._debate_repo.assign_legacy_debates_to_user(user.id)
                except Exception:
                    logger.warning(
                        "Failed to assign pre-auth legacy debates to initial administrator %s",
                        user.id,
                        exc_info=True,
                    )

            token = self._token_service.create_access_token(
                user_id=user.id,
                username=user.username,
                is_admin=user.is_admin,
                token_version=user.token_version,
            )
            return token, user

    async def authenticate(self, username: str, password: str) -> Tuple[str, User]:
        """
        Authenticates username and password.
        Returns access token and user entity.
        Resistant to user-enumeration timing attacks.
        """
        user = await self._user_repo.get_by_username(username)
        if not user:
            # Perform dummy verify in thread to equalize execution time against timing attacks
            await asyncio.to_thread(self._hasher.verify, password, _DUMMY_HASH)
            raise InvalidCredentialsError("Invalid username or password.")

        is_valid = await asyncio.to_thread(self._hasher.verify, password, user.password_hash)
        if not is_valid:
            raise InvalidCredentialsError("Invalid username or password.")

        if not user.is_active:
            raise UserInactiveError("This user account is inactive.")

        token = self._token_service.create_access_token(
            user_id=user.id,
            username=user.username,
            is_admin=user.is_admin,
            token_version=user.token_version,
        )
        return token, user

    async def validate_token(self, token: str) -> Optional[User]:
        """
        Validates token string and resolves corresponding active User.
        Enforces session revocation by checking token_version against current database record.
        """
        payload = self._token_service.decode_and_validate_token(token)
        if not payload:
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        user = await self._user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            return None

        # Session Revocation Check (M1): compare token_version
        token_version = payload.get("token_version", 1)
        if user.token_version != token_version:
            return None

        return user

    async def create_user(
        self,
        actor: User,
        username: str,
        password: str,
        is_admin: bool = False,
    ) -> User:
        """
        Allows an administrator to create a new user.
        """
        if not actor.is_admin:
            raise UnauthorizedError("Only administrators can create new users.")

        if len(password) < 8:
            raise WeakPasswordError(_WEAK_PASSWORD_MSG)

        user_id = str(uuid.uuid4())
        password_hash = await asyncio.to_thread(self._hasher.hash, password)
        new_user = User(
            id=user_id,
            username=username,
            password_hash=password_hash,
            is_admin=is_admin,
            is_active=True,
            token_version=1,
        )
        await self._user_repo.save(new_user)
        return new_user

    async def list_users(self, actor: User) -> list[User]:
        """
        Lists all users (administrator only).
        """
        if not actor.is_admin:
            raise UnauthorizedError("Only administrators can list users.")
        return await self._user_repo.list_users()

    @staticmethod
    def _validate_self_update(
        actor: User,
        target: User,
        is_active: Optional[bool],
        is_admin: Optional[bool],
    ) -> None:
        if actor.id != target.id:
            return
        if is_active is False:
            raise SelfModificationError("Cannot deactivate your own administrator account.")
        if is_admin is False:
            raise SelfModificationError("Cannot revoke administrator privileges from your own account.")

    async def _ensure_not_last_admin(self, target: User, error_msg: str) -> None:
        all_users = await self._user_repo.list_users()
        active_admins = [u for u in all_users if u.is_admin and u.is_active]
        if len(active_admins) <= 1 and any(u.id == target.id for u in active_admins):
            raise LastAdminError(error_msg)

    async def _resolve_password_update(
        self,
        target: User,
        password: Optional[str],
    ) -> Tuple[str, int]:
        if password is None:
            return target.password_hash, target.token_version
        if len(password) < 8:
            raise WeakPasswordError(_WEAK_PASSWORD_MSG)
        new_hash = await asyncio.to_thread(self._hasher.hash, password)
        return new_hash, target.token_version + 1

    async def update_user(
        self,
        actor: User,
        user_id: str,
        is_admin: Optional[bool] = None,
        is_active: Optional[bool] = None,
        password: Optional[str] = None,
    ) -> User:
        """
        Updates user attributes (admin only).
        Guards:
        - Non-admins cannot update users.
        - Cannot deactivate or demote own account.
        - Cannot deactivate or demote the last active administrator.
        - Password >= 8 characters (resets token_version to revoke existing sessions).
        """
        if not actor.is_admin:
            raise UnauthorizedError("Only administrators can update users.")

        target = await self._user_repo.get_by_id(user_id)
        if not target:
            raise UserNotFoundError(f"User '{user_id}' not found.")

        self._validate_self_update(actor, target, is_active, is_admin)

        will_demote = is_admin is False and target.is_admin
        will_deactivate = is_active is False and target.is_admin and target.is_active
        if will_demote or will_deactivate:
            await self._ensure_not_last_admin(
                target,
                "Cannot demote or deactivate the last active administrator.",
            )

        new_password_hash, new_token_version = await self._resolve_password_update(target, password)
        new_deleted_at = None if is_active is True else target.deleted_at

        updated_target = User(
            id=target.id,
            username=target.username,
            password_hash=new_password_hash,
            is_admin=target.is_admin if is_admin is None else is_admin,
            is_active=target.is_active if is_active is None else is_active,
            token_version=new_token_version,
            deleted_at=new_deleted_at,
            created_at=target.created_at,
        )

        await self._user_repo.save(updated_target)
        return updated_target

    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
    ) -> Tuple[str, User]:
        """
        Allows an authenticated user to change their own password.
        Increments token_version to invalidate prior session tokens and returns
        a fresh (access_token, updated_user) tuple for the active session.
        """
        if len(new_password) < 8:
            raise WeakPasswordError("New password must be at least 8 characters long.")

        user = await self._user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            raise UserNotFoundError(f"User '{user_id}' not found or inactive.")

        is_valid = await asyncio.to_thread(self._hasher.verify, current_password, user.password_hash)
        if not is_valid:
            raise InvalidCredentialsError("Current password is incorrect.")

        new_hash = await asyncio.to_thread(self._hasher.hash, new_password)
        updated = User(
            id=user.id,
            username=user.username,
            password_hash=new_hash,
            is_admin=user.is_admin,
            is_active=user.is_active,
            token_version=user.token_version + 1,
            deleted_at=user.deleted_at,
            created_at=user.created_at,
        )
        await self._user_repo.save(updated)

        new_token = self._token_service.create_access_token(
            user_id=updated.id,
            username=updated.username,
            is_admin=updated.is_admin,
            token_version=updated.token_version,
        )
        return new_token, updated

    def _purge_user_resources(self, user_id: str) -> None:
        for repo in (self._debate_repo, self._agent_config_repo):
            if repo:
                try:
                    repo.delete_by_user_id(user_id)
                except Exception:
                    logger.warning(
                        "Failed to purge user %s resources from %s",
                        user_id,
                        type(repo).__name__,
                        exc_info=True,
                    )

    async def delete_user(self, actor: User, user_id: str) -> str:
        """
        Deletes a user according to configured strategy (admin only).
        Guards:
        - Non-admins cannot delete users.
        - Cannot delete own account.
        - Cannot delete the last active administrator.
        Returns:
            "soft" if soft-deleted (is_active set to False and deleted_at set),
            or "hard" if permanently deleted from database along with debates and configs.
        """
        if not actor.is_admin:
            raise UnauthorizedError("Only administrators can delete users.")

        target = await self._user_repo.get_by_id(user_id)
        if not target:
            raise UserNotFoundError(f"User '{user_id}' not found.")

        if actor.id == target.id:
            raise SelfModificationError("Cannot delete your own administrator account.")

        if target.is_admin:
            await self._ensure_not_last_admin(
                target,
                "Cannot delete the last active administrator.",
            )

        if self._delete_strategy.lower() == "hard":
            await self._user_repo.delete(user_id)
            self._purge_user_resources(user_id)
            return "hard"

        updated_target = User(
            id=target.id,
            username=target.username,
            password_hash=target.password_hash,
            is_admin=target.is_admin,
            is_active=False,
            token_version=target.token_version,
            deleted_at=datetime.now(timezone.utc),
            created_at=target.created_at,
        )
        await self._user_repo.save(updated_target)
        return "soft"
