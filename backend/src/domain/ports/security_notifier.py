"""
Domain Port: ISecurityNotifier
Defines abstract interface for dispatching security and authentication alerts.
"""
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class ISecurityNotifier(Protocol):
    """Port for sending security notifications and audit alerts."""

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
        """
        Alert for a login attempt (successful or failed).
        Returns True if alert was dispatched successfully, False otherwise.
        """
        ...

    async def notify_rate_limit(
        self,
        *,
        client_ip: str,
        endpoint: str,
        user_agent: Optional[str] = None,
        country: Optional[str] = None,
    ) -> bool:
        """
        Alert when a client exceeds rate limits.
        Returns True if alert was dispatched successfully, False otherwise.
        """
        ...

