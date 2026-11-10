from dataclasses import dataclass, field
from datetime import datetime, timezone
import re
from typing import Optional
import unicodedata

_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_\-\.]{3,50}$")


@dataclass(frozen=True)
class User:
    id: str
    username: str
    password_hash: str
    is_admin: bool = False
    is_active: bool = True
    token_version: int = 1
    deleted_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        normalized = unicodedata.normalize("NFKC", self.username).strip().lower()
        if not _USERNAME_PATTERN.match(normalized):
            raise ValueError(
                f"Invalid username '{self.username}': must be 3-50 alphanumeric characters (or _, -, .)"
            )
        object.__setattr__(self, "username", normalized)
