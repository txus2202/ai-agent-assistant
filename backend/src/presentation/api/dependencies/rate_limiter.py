import time
from collections import defaultdict
from typing import Callable, Optional
from fastapi import HTTPException, Request, status


class InMemoryRateLimiter:
    """In-memory sliding-window log rate limiter with lazy eviction."""

    def __init__(self) -> None:
        self._history: dict[str, list[float]] = defaultdict(list)

    def check_rate_limit(
        self,
        key: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, int]:
        """
        Evaluate if a request under `key` is allowed.
        Returns:
            (is_allowed: bool, retry_after_seconds: int)
        """
        now = time.monotonic()
        cutoff = now - window_seconds

        timestamps = [ts for ts in self._history[key] if ts > cutoff]

        if len(timestamps) >= max_requests:
            oldest = timestamps[0]
            retry_after = int(window_seconds - (now - oldest)) + 1
            self._history[key] = timestamps
            return False, max(1, retry_after)

        timestamps.append(now)
        self._history[key] = timestamps

        # Periodic cleanup of empty keys if memory usage grows
        if len(self._history) > 10000:
            stale_keys = [k for k, v in self._history.items() if not v or v[-1] <= cutoff]
            for k in stale_keys:
                del self._history[k]

        return True, 0

    def reset_key(self, key: str) -> None:
        self._history.pop(key, None)

    def reset(self) -> None:
        self._history.clear()


# Default singleton rate limiter for auth endpoints
default_rate_limiter = InMemoryRateLimiter()


def get_client_ip(request: Request, trust_x_forwarded_for: bool = False) -> str:
    """Resolve client IP address, only trusting X-Forwarded-For when explicitly configured."""
    if trust_x_forwarded_for:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    if request.client and getattr(request.client, "host", None):
        return request.client.host
    return "unknown"


def enforce_rate_limit(
    request: Request,
    max_requests: int,
    window_seconds: int,
    limiter: Optional[InMemoryRateLimiter] = None,
    key_prefix: str = "rate_limit",
    trust_x_forwarded_for: bool = False,
) -> None:
    """Directly enforce rate limits for a request without allocating a closure per call."""
    active_limiter = limiter or default_rate_limiter
    client_ip = get_client_ip(request, trust_x_forwarded_for=trust_x_forwarded_for)
    key = f"{key_prefix}:{client_ip}"
    allowed, retry_after = active_limiter.check_rate_limit(
        key=key,
        max_requests=max_requests,
        window_seconds=window_seconds,
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )


def create_rate_limiter(
    max_requests: int,
    window_seconds: int,
    limiter: Optional[InMemoryRateLimiter] = None,
    key_prefix: str = "rate_limit",
    trust_x_forwarded_for: bool = False,
) -> Callable:
    """FastAPI dependency factory enforcing rate limits by client IP."""
    async def _rate_limit_dependency(request: Request) -> None:
        enforce_rate_limit(
            request=request,
            max_requests=max_requests,
            window_seconds=window_seconds,
            limiter=limiter,
            key_prefix=key_prefix,
            trust_x_forwarded_for=trust_x_forwarded_for,
        )

    return _rate_limit_dependency

