from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from src.domain.ports.password_hasher_port import IPasswordHasher


MAX_PASSWORD_LENGTH = 128


class Argon2idPasswordHasher(IPasswordHasher):
    """
    Argon2id implementation using argon2-cffi.
    Configured with OWASP recommendations (time_cost=2, memory_cost=65536, parallelism=2).
    """

    def __init__(
        self,
        time_cost: int = 2,
        memory_cost: int = 65536,
        parallelism: int = 2,
        hash_len: int = 32,
        salt_len: int = 16,
    ) -> None:
        self._ph = PasswordHasher(
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism,
            hash_len=hash_len,
            salt_len=salt_len,
        )

    def hash(self, plain_password: str) -> str:
        if not plain_password or "\x00" in plain_password:
            raise ValueError("Password cannot be empty or contain null bytes.")
        if len(plain_password) > MAX_PASSWORD_LENGTH:
            raise ValueError(f"Password cannot exceed {MAX_PASSWORD_LENGTH} characters.")
        return self._ph.hash(plain_password)

    def verify(self, plain_password: str, hashed_password: str) -> bool:
        if (
            not hashed_password
            or not plain_password
            or "\x00" in plain_password
            or len(plain_password) > MAX_PASSWORD_LENGTH
        ):
            return False
        try:
            return self._ph.verify(hashed_password, plain_password)
        except (VerifyMismatchError, InvalidHashError, ValueError):
            return False

