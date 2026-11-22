"""
Infrastructure: Telegram Security Notifier
Dispatches security and authentication events to a Telegram chat via Telegram Bot API.
Includes configurable event triggers, consecutive failure thresholds, and anti-spam throttling.
"""
from __future__ import annotations

import html
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

import httpx

from src.domain.ports.security_notifier import ISecurityNotifier

logger = logging.getLogger(__name__)


class TelegramSecurityNotifier(ISecurityNotifier):
    """
    Sends security alerts to Telegram using Telegram Bot API.
    Fails safely without raising unhandled exceptions to protect application flow.
    Supports granular event filters, failure thresholds, and anti-spam throttling.
    """

    def __init__(
        self,
        bot_token: str = "",
        chat_id: str = "",
        enabled: bool = True,
        alert_on_login_success: bool = True,
        alert_admin_only_success: bool = False,
        alert_on_login_failure: bool = True,
        failed_login_threshold: int = 1,
        alert_on_rate_limit: bool = True,
        throttle_seconds: int = 60,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.bot_token = bot_token.strip().strip('"').strip("'") if bot_token else ""
        self.chat_id = chat_id.strip().strip('"').strip("'") if chat_id else ""
        self.enabled = bool(enabled and self.bot_token and self.chat_id)

        # Configurable event filters
        self.alert_on_login_success = alert_on_login_success
        self.alert_admin_only_success = alert_admin_only_success
        self.alert_on_login_failure = alert_on_login_failure
        self.failed_login_threshold = max(1, failed_login_threshold)
        self.alert_on_rate_limit = alert_on_rate_limit
        self.throttle_seconds = max(0, throttle_seconds)

        self._http_client = http_client

        # Internal state for anti-spam throttling and failure counters
        self._last_alert_time: dict[str, float] = {}
        self._suppressed_counts: dict[str, int] = defaultdict(int)
        self._failure_counts: dict[str, int] = defaultdict(int)

    def _should_throttle(self, key: str) -> tuple[bool, int]:
        """
        Check if an alert under `key` should be throttled.
        Returns:
            (is_throttled: bool, suppressed_count_from_previous_silenced: int)
        """
        if self.throttle_seconds <= 0:
            return False, 0

        now = time.monotonic()
        last_sent = self._last_alert_time.get(key)

        if last_sent is not None and (now - last_sent) < self.throttle_seconds:
            self._suppressed_counts[key] += 1
            return True, 0

        # Cooldown expired or first time
        suppressed = self._suppressed_counts.pop(key, 0)
        self._last_alert_time[key] = now

        # Periodic cleanup of expired cache entries to prevent memory leaks
        if len(self._last_alert_time) > 1000:
            cutoff = now - (self.throttle_seconds * 2)
            stale_keys = [k for k, t in self._last_alert_time.items() if t < cutoff]
            for k in stale_keys:
                self._last_alert_time.pop(k, None)
                self._suppressed_counts.pop(k, None)

        return False, suppressed

    async def _send_message(self, text: str) -> bool:
        if not self.enabled:
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            if self._http_client:
                response = await self._http_client.post(url, json=payload, timeout=5.0)
            else:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.post(url, json=payload)

            if response.status_code >= 400:
                logger.warning(
                    "Telegram alert failed with status %d (chat_id: %s)",
                    response.status_code,
                    self.chat_id,
                )
                return False
            return True
        except Exception as exc:
            logger.warning(
                "Failed to dispatch Telegram security alert (chat_id: %s): %s",
                self.chat_id,
                exc,
            )
            return False

    async def notify_login_attempt(
        self,
        *,
        username: str,
        client_ip: str,
        success: bool,
        is_admin: bool = False,
        user_agent: Optional[str] = None,
        country: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> bool:
        if not self.enabled:
            return False

        user_key = f"{client_ip}:{username}"

        # ── 1. Evaluate filter rules ───────────────────────────────────────
        if success:
            # Reset failure count on success
            self._failure_counts.pop(user_key, None)

            if not self.alert_on_login_success:
                return False
            if self.alert_admin_only_success and not is_admin:
                return False
        else:
            if not self.alert_on_login_failure:
                return False

            self._failure_counts[user_key] += 1
            current_failures = self._failure_counts[user_key]

            # If threshold > 1, only alert once the threshold is reached
            if current_failures < self.failed_login_threshold:
                return False

        # ── 2. Anti-spam Throttling ────────────────────────────────────────
        throttle_key = f"login:{'success' if success else 'fail'}:{client_ip}"
        is_throttled, previous_suppressed = self._should_throttle(throttle_key)
        if is_throttled:
            return False

        # ── 3. Build alert content ─────────────────────────────────────────
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        status_label = "Inicio de sesión exitoso ✅" if success else "Intento de inicio de sesión fallido ❌"
        icon = "🔐" if success else "🚨"

        lines = [
            f"{icon} <b>Atenea Security Alert</b>",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"<b>Evento:</b> {status_label}",
            f"<b>Usuario:</b> <code>{html.escape(username or 'desconocido')}</code>",
        ]

        if success and is_admin:
            lines.append("<b>Rol:</b> 👑 <b>Administrador</b>")

        lines.append(f"<b>IP:</b> <code>{html.escape(client_ip or 'unknown')}</code>")
        if country:
            lines.append(f"<b>País:</b> <code>{html.escape(country)}</code>")
        lines.append(f"<b>Fecha:</b> <code>{now_str}</code>")

        if not success:
            current_failures = self._failure_counts.get(user_key, 1)
            if current_failures > 1:
                lines.append(f"<b>Intentos fallidos acumulados:</b> {current_failures}")
            if reason:
                lines.append(f"<b>Motivo:</b> {html.escape(reason)}")

        if user_agent:
            ua = user_agent[:200] + ("..." if len(user_agent) > 200 else "")
            lines.append(f"<b>Dispositivo:</b> <i>{html.escape(ua)}</i>")

        if previous_suppressed > 0:
            lines.append(
                f"\n⚠️ <i>Nota: Se han agrupado y omitido {previous_suppressed} alertas similares en los últimos {self.throttle_seconds}s para evitar saturación.</i>"
            )

        return await self._send_message("\n".join(lines))

    async def notify_rate_limit(
        self,
        *,
        client_ip: str,
        endpoint: str,
        user_agent: Optional[str] = None,
        country: Optional[str] = None,
    ) -> bool:
        if not self.enabled:
            return False

        if not self.alert_on_rate_limit:
            return False

        # Anti-spam Throttling
        throttle_key = f"ratelimit:{endpoint}:{client_ip}"
        is_throttled, previous_suppressed = self._should_throttle(throttle_key)
        if is_throttled:
            return False

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        lines = [
            "⛔ <b>Atenea Security Alert</b>",
            "━━━━━━━━━━━━━━━━━━━━━",
            "<b>Evento:</b> Límite de peticiones superado (HTTP 429) 🚫",
            f"<b>Endpoint:</b> <code>{html.escape(endpoint)}</code>",
            f"<b>IP:</b> <code>{html.escape(client_ip or 'unknown')}</code>",
        ]
        if country:
            lines.append(f"<b>País:</b> <code>{html.escape(country)}</code>")
        lines.append(f"<b>Fecha:</b> <code>{now_str}</code>")

        if user_agent:
            ua = user_agent[:200] + ("..." if len(user_agent) > 200 else "")
            lines.append(f"<b>Dispositivo:</b> <i>{html.escape(ua)}</i>")

        if previous_suppressed > 0:
            lines.append(
                f"\n⚠️ <i>Nota: Se han agrupado y omitido {previous_suppressed} peticiones bloqueadas adicionales en los últimos {self.throttle_seconds}s.</i>"
            )

        return await self._send_message("\n".join(lines))
