import pytest
import httpx
from unittest.mock import AsyncMock, patch

from src.infrastructure.security.telegram_notifier import TelegramSecurityNotifier


@pytest.mark.asyncio
async def test_telegram_notifier_disabled_when_empty_credentials():
    notifier = TelegramSecurityNotifier(bot_token="", chat_id="", enabled=True)
    assert notifier.enabled is False

    res = await notifier.notify_login_attempt(
        username="admin",
        client_ip="127.0.0.1",
        success=True,
    )
    assert res is False

    rate_res = await notifier.notify_rate_limit(
        client_ip="127.0.0.1",
        endpoint="/api/auth/login",
    )
    assert rate_res is False


@pytest.mark.asyncio
async def test_telegram_notifier_notify_login_success():
    mock_post = AsyncMock(return_value=httpx.Response(200, json={"ok": True}))
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = mock_post

    notifier = TelegramSecurityNotifier(
        bot_token="test_token",
        chat_id="123456",
        enabled=True,
        http_client=mock_client,
    )

    success = await notifier.notify_login_attempt(
        username="profesor",
        client_ip="198.51.100.1",
        success=True,
        user_agent="Mozilla/5.0 (Macintosh)",
        country="ES",
    )
    assert success is True
    assert mock_post.await_count == 1

    call_args = mock_post.call_args
    assert call_args[0][0] == "https://api.telegram.org/bottest_token/sendMessage"
    payload = call_args[1]["json"]
    assert payload["chat_id"] == "123456"
    assert "Inicio de sesión exitoso ✅" in payload["text"]
    assert "profesor" in payload["text"]
    assert "198.51.100.1" in payload["text"]
    assert "ES" in payload["text"]
    assert "Mozilla/5.0" in payload["text"]


@pytest.mark.asyncio
async def test_telegram_notifier_notify_login_failure():
    mock_post = AsyncMock(return_value=httpx.Response(200, json={"ok": True}))
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = mock_post

    notifier = TelegramSecurityNotifier(
        bot_token="test_token",
        chat_id="123456",
        enabled=True,
        http_client=mock_client,
    )

    success = await notifier.notify_login_attempt(
        username="unknown_user",
        client_ip="203.0.113.5",
        success=False,
        reason="Credenciales inválidas",
        country="FR",
    )
    assert success is True
    payload = mock_post.call_args[1]["json"]
    assert "Intento de inicio de sesión fallido ❌" in payload["text"]
    assert "unknown_user" in payload["text"]
    assert "Credenciales inválidas" in payload["text"]
    assert "FR" in payload["text"]


@pytest.mark.asyncio
async def test_telegram_notifier_notify_rate_limit():
    mock_post = AsyncMock(return_value=httpx.Response(200, json={"ok": True}))
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = mock_post

    notifier = TelegramSecurityNotifier(
        bot_token="test_token",
        chat_id="123456",
        enabled=True,
        http_client=mock_client,
    )

    success = await notifier.notify_rate_limit(
        client_ip="203.0.113.10",
        endpoint="/api/auth/login",
        user_agent="BadBot/1.0",
        country="DE",
    )
    assert success is True
    payload = mock_post.call_args[1]["json"]
    assert "Límite de peticiones superado (HTTP 429) 🚫" in payload["text"]
    assert "/api/auth/login" in payload["text"]
    assert "203.0.113.10" in payload["text"]
    assert "DE" in payload["text"]


@pytest.mark.asyncio
async def test_telegram_notifier_admin_only_success_filter():
    mock_post = AsyncMock(return_value=httpx.Response(200, json={"ok": True}))
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = mock_post

    notifier = TelegramSecurityNotifier(
        bot_token="test_token",
        chat_id="123456",
        enabled=True,
        alert_admin_only_success=True,
        http_client=mock_client,
    )

    # 1. Non-admin login -> suppressed
    res1 = await notifier.notify_login_attempt(
        username="regular_student",
        client_ip="1.2.3.4",
        success=True,
        is_admin=False,
    )
    assert res1 is False
    assert mock_post.await_count == 0

    # 2. Admin login -> sent
    res2 = await notifier.notify_login_attempt(
        username="admin_profesor",
        client_ip="1.2.3.4",
        success=True,
        is_admin=True,
    )
    assert res2 is True
    assert mock_post.await_count == 1
    assert "👑 <b>Administrador</b>" in mock_post.call_args[1]["json"]["text"]


@pytest.mark.asyncio
async def test_telegram_notifier_failed_login_threshold():
    mock_post = AsyncMock(return_value=httpx.Response(200, json={"ok": True}))
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = mock_post

    notifier = TelegramSecurityNotifier(
        bot_token="test_token",
        chat_id="123456",
        enabled=True,
        failed_login_threshold=3,
        throttle_seconds=0,  # disable throttle to test threshold purely
        http_client=mock_client,
    )

    # Attempt 1: failure -> below threshold (no alert)
    res1 = await notifier.notify_login_attempt(
        username="target_user",
        client_ip="192.0.2.1",
        success=False,
    )
    assert res1 is False
    assert mock_post.await_count == 0

    # Attempt 2: failure -> below threshold (no alert)
    res2 = await notifier.notify_login_attempt(
        username="target_user",
        client_ip="192.0.2.1",
        success=False,
    )
    assert res2 is False
    assert mock_post.await_count == 0

    # Attempt 3: failure -> reaches threshold 3 (alerts!)
    res3 = await notifier.notify_login_attempt(
        username="target_user",
        client_ip="192.0.2.1",
        success=False,
    )
    assert res3 is True
    assert mock_post.await_count == 1
    assert "<b>Intentos fallidos acumulados:</b> 3" in mock_post.call_args[1]["json"]["text"]

    # Now success resets failure counter
    await notifier.notify_login_attempt(
        username="target_user",
        client_ip="192.0.2.1",
        success=True,
    )
    assert notifier._failure_counts.get("192.0.2.1:target_user") is None


@pytest.mark.asyncio
async def test_telegram_notifier_anti_spam_throttling():
    mock_post = AsyncMock(return_value=httpx.Response(200, json={"ok": True}))
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = mock_post

    notifier = TelegramSecurityNotifier(
        bot_token="test_token",
        chat_id="123456",
        enabled=True,
        throttle_seconds=60,
        http_client=mock_client,
    )

    # First alert -> sent immediately
    res1 = await notifier.notify_login_attempt(
        username="attacker",
        client_ip="10.0.0.1",
        success=False,
    )
    assert res1 is True
    assert mock_post.await_count == 1

    # Second and third rapid attempts within 60s -> suppressed by throttling
    res2 = await notifier.notify_login_attempt(
        username="attacker",
        client_ip="10.0.0.1",
        success=False,
    )
    res3 = await notifier.notify_login_attempt(
        username="attacker",
        client_ip="10.0.0.1",
        success=False,
    )
    assert res2 is False
    assert res3 is False
    assert mock_post.await_count == 1

    # Simulate cooldown expiration: manually backdate last alert time
    throttle_key = "login:fail:10.0.0.1"
    notifier._last_alert_time[throttle_key] -= 65

    # Fourth attempt -> sends and includes the suppressed count notice
    res4 = await notifier.notify_login_attempt(
        username="attacker",
        client_ip="10.0.0.1",
        success=False,
    )
    assert res4 is True
    assert mock_post.await_count == 2
    last_text = mock_post.call_args[1]["json"]["text"]
    assert "Se han agrupado y omitido 2 alertas similares" in last_text


@pytest.mark.asyncio
async def test_telegram_notifier_handles_http_error_gracefully():
    mock_post = AsyncMock(return_value=httpx.Response(400, text="Bad Request"))
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = mock_post

    notifier = TelegramSecurityNotifier(
        bot_token="test_token",
        chat_id="123456",
        enabled=True,
        http_client=mock_client,
    )

    success = await notifier.notify_login_attempt(
        username="admin",
        client_ip="127.0.0.1",
        success=True,
    )
    assert success is False


@pytest.mark.asyncio
async def test_telegram_notifier_handles_network_exception_gracefully():
    mock_post = AsyncMock(side_effect=httpx.ConnectTimeout("Connection timed out"))
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.post = mock_post

    notifier = TelegramSecurityNotifier(
        bot_token="test_token",
        chat_id="123456",
        enabled=True,
        http_client=mock_client,
    )

    success = await notifier.notify_login_attempt(
        username="admin",
        client_ip="127.0.0.1",
        success=True,
    )
    assert success is False
