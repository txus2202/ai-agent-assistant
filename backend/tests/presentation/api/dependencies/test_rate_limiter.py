import time
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException, Request, status
from src.presentation.api.dependencies.rate_limiter import (
    InMemoryRateLimiter,
    create_rate_limiter,
)


def test_rate_limiter_allows_under_limit():
    limiter = InMemoryRateLimiter()
    key = "ip:127.0.0.1"

    allowed, retry_after = limiter.check_rate_limit(key, max_requests=3, window_seconds=60)
    assert allowed is True
    assert retry_after == 0

    allowed, retry_after = limiter.check_rate_limit(key, max_requests=3, window_seconds=60)
    assert allowed is True
    assert retry_after == 0

    allowed, retry_after = limiter.check_rate_limit(key, max_requests=3, window_seconds=60)
    assert allowed is True
    assert retry_after == 0


def test_rate_limiter_blocks_over_limit():
    limiter = InMemoryRateLimiter()
    key = "ip:127.0.0.1"

    for _ in range(3):
        allowed, _ = limiter.check_rate_limit(key, max_requests=3, window_seconds=60)
        assert allowed is True

    # 4th request must be blocked
    allowed, retry_after = limiter.check_rate_limit(key, max_requests=3, window_seconds=60)
    assert allowed is False
    assert 1 <= retry_after <= 60


def test_rate_limiter_distinct_keys():
    limiter = InMemoryRateLimiter()
    key_a = "ip:1.1.1.1"
    key_b = "ip:2.2.2.2"

    for _ in range(3):
        limiter.check_rate_limit(key_a, max_requests=3, window_seconds=60)

    # Key A is blocked
    allowed_a, _ = limiter.check_rate_limit(key_a, max_requests=3, window_seconds=60)
    assert allowed_a is False

    # Key B is still allowed
    allowed_b, _ = limiter.check_rate_limit(key_b, max_requests=3, window_seconds=60)
    assert allowed_b is True


def test_rate_limiter_window_expiration(monkeypatch):
    limiter = InMemoryRateLimiter()
    key = "ip:127.0.0.1"
    fake_time = 1000.0

    monkeypatch.setattr(time, "monotonic", lambda: fake_time)

    for _ in range(2):
        allowed, _ = limiter.check_rate_limit(key, max_requests=2, window_seconds=10)
        assert allowed is True

    # Blocked at t=1000.0
    allowed, retry_after = limiter.check_rate_limit(key, max_requests=2, window_seconds=10)
    assert allowed is False

    # Advance time past window (t=1011.0)
    fake_time = 1011.0
    allowed, retry_after = limiter.check_rate_limit(key, max_requests=2, window_seconds=10)
    assert allowed is True
    assert retry_after == 0


@pytest.mark.asyncio
async def test_fastapi_rate_limiter_dependency_raises_429():
    limiter = InMemoryRateLimiter()
    dep = create_rate_limiter(max_requests=2, window_seconds=60, limiter=limiter, key_prefix="test")

    mock_request = MagicMock(spec=Request)
    mock_request.headers = {}
    mock_request.client.host = "192.168.1.10"

    # 1st and 2nd pass
    await dep(mock_request)
    await dep(mock_request)

    # 3rd must raise 429
    with pytest.raises(HTTPException) as exc_info:
        await dep(mock_request)

    assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Retry-After" in exc_info.value.headers
    assert exc_info.value.detail == "Too many requests. Please try again later."


@pytest.mark.asyncio
async def test_rate_limiter_ignores_spoofed_x_forwarded_for_by_default():
    limiter = InMemoryRateLimiter()
    dep = create_rate_limiter(
        max_requests=2,
        window_seconds=60,
        limiter=limiter,
        key_prefix="test",
        trust_x_forwarded_for=False,
    )

    # Attacker keeps rotating X-Forwarded-For while connecting from same socket IP 10.0.0.5
    for spoof_ip in ("1.1.1.1", "2.2.2.2"):
        req = MagicMock(spec=Request)
        req.headers = {"X-Forwarded-For": spoof_ip}
        req.client.host = "10.0.0.5"
        await dep(req)

    # 3rd attempt with yet another spoofed X-Forwarded-For must still be blocked
    req3 = MagicMock(spec=Request)
    req3.headers = {"X-Forwarded-For": "3.3.3.3"}
    req3.client.host = "10.0.0.5"
    with pytest.raises(HTTPException) as exc_info:
        await dep(req3)
    assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS


