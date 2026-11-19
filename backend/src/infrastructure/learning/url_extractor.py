"""
Infrastructure Adapter: URLExtractor

Fetches a web page with httpx and extracts clean text using
beautifulsoup4 (html.parser), enforcing SSRF protections and download size limits.
"""
from __future__ import annotations

import ipaddress
import socket
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

from src.domain.exceptions import ExtractionError

ALLOWED_SCHEMES = frozenset({"http", "https"})
MAX_REDIRECTS = 5
DEFAULT_MAX_DOWNLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
_REDIRECT_STATUS_CODES = frozenset({301, 302, 303, 307, 308})


def _is_forbidden_ip(ip_str: str) -> bool:
    """Return True if ``ip_str`` refers to any non-public/internal address."""
    clean_ip = ip_str.split("%", 1)[0]
    try:
        addr = ipaddress.ip_address(clean_ip)
    except ValueError:
        return True

    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped

    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
        or not addr.is_global
    )


def _parse_and_check_url_parts(url: str) -> tuple[str, int]:
    """Validate URL syntax, scheme, credentials, host allowlist, and port."""
    if not isinstance(url, str) or not url.strip():
        raise ExtractionError("URL must be a non-empty string")
    if any(ch.isspace() or ord(ch) < 32 for ch in url):
        raise ExtractionError("URL contains invalid control or whitespace characters")

    parsed = urlsplit(url)
    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise ExtractionError(f"Unsupported URL scheme '{parsed.scheme}'. Only HTTP/HTTPS allowed.")

    if parsed.username is not None or parsed.password is not None:
        raise ExtractionError("URLs containing embedded credentials are not allowed")

    hostname = parsed.hostname
    if not hostname:
        raise ExtractionError("URL must contain a valid hostname")

    host_lower = hostname.lower().rstrip(".")
    if host_lower == "localhost" or host_lower.endswith((".localhost", ".local", ".internal")):
        raise ExtractionError(f"Blocked internal or local hostname: {hostname}")

    try:
        port = parsed.port or (443 if scheme == "https" else 80)
    except ValueError as exc:
        raise ExtractionError(f"Invalid URL port: {exc}") from exc
    return hostname, port


def _validate_resolved_addresses(hostname: str, port: int) -> None:
    """Resolve DNS entries for ``hostname`` and reject any non-global target IP."""
    try:
        addr_infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ExtractionError(f"DNS resolution failed for '{hostname}': {exc}") from exc

    if not addr_infos:
        raise ExtractionError(f"DNS resolution returned no addresses for '{hostname}'")

    for _, _, _, _, sockaddr in addr_infos:
        resolved_ip = str(sockaddr[0])
        if _is_forbidden_ip(resolved_ip):
            raise ExtractionError(
                f"Blocked SSRF target IP address '{resolved_ip}' for host '{hostname}'"
            )


def _validate_url_target(url: str) -> None:
    """Validate URL scheme, hostname, and resolved DNS IP addresses against SSRF."""
    hostname, port = _parse_and_check_url_parts(url)
    _validate_resolved_addresses(hostname, port)


def _import_url_deps() -> tuple[Any, Any]:
    """Import ``httpx`` and ``beautifulsoup4`` lazily."""
    try:
        import httpx  # noqa: PLC0415
    except ImportError as exc:
        raise ExtractionError(
            "httpx is not installed. Run: pip install httpx"
        ) from exc

    try:
        import bs4  # noqa: PLC0415
    except ImportError as exc:
        raise ExtractionError(
            "beautifulsoup4 is not installed. Run: pip install beautifulsoup4"
        ) from exc
    return httpx, bs4


def _resolve_redirect_target(response: Any, current_url: str) -> str | None:
    """Return resolved redirect target if ``response`` is a redirect, else None."""
    if getattr(response, "status_code", None) not in _REDIRECT_STATUS_CODES:
        return None
    headers = getattr(response, "headers", {})
    location = headers.get("location") if headers is not None else None
    if not isinstance(location, str) or not location.strip():
        raise ExtractionError("Redirect response missing Location header")
    return urljoin(current_url, location.strip())


def _assert_within_size_limit(byte_len: int, max_bytes: int, label: str) -> None:
    if byte_len > max_bytes:
        raise ExtractionError(f"{label} exceeds maximum allowed limit ({max_bytes} bytes)")


def _extract_verified_html(response: Any, max_bytes: int) -> str:
    """Enforce status code and download size limits before returning HTML text."""
    headers = getattr(response, "headers", None)
    raw_cl = headers.get("content-length") if headers is not None else None
    if isinstance(raw_cl, (str, int)):
        cl_str = str(raw_cl).strip()
        if cl_str.isdigit():
            _assert_within_size_limit(int(cl_str), max_bytes, "Response Content-Length")

    response.raise_for_status()

    raw_content = getattr(response, "content", None)
    if isinstance(raw_content, (bytes, bytearray)):
        _assert_within_size_limit(len(raw_content), max_bytes, "Response size")

    html_text: str = response.text
    if isinstance(html_text, str):
        _assert_within_size_limit(len(html_text.encode("utf-8", errors="ignore")), max_bytes, "Response size")
    return html_text


def _fetch_final_html(httpx_mod: Any, start_url: str, max_bytes: int) -> str:
    """Follow bounded SSRF-validated redirects and return the response HTML text."""
    current_url = start_url
    for _ in range(MAX_REDIRECTS + 1):
        _validate_url_target(current_url)
        response = httpx_mod.get(current_url, follow_redirects=False, timeout=30)
        redirect_target = _resolve_redirect_target(response, current_url)
        if redirect_target is not None:
            current_url = redirect_target
            continue
        return _extract_verified_html(response, max_bytes)
    raise ExtractionError(f"Exceeded maximum number of redirects ({MAX_REDIRECTS})")


class URLExtractor:
    """Fetches and strips HTML from a URL safely, returning plain text."""

    @staticmethod
    def extract(
        url: str | Path,
        max_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
        **_kwargs: Any,
    ) -> str:
        """
        Fetch ``url`` and return its visible text content.

        Args:
            url: HTTP/HTTPS URL to fetch.
            max_bytes: Maximum allowed response payload size in bytes.

        Returns:
            Plain text extracted from the page body.

        Raises:
            ExtractionError: On SSRF violation, unsafe redirect, size overflow,
                             network failure, bad HTTP status, or parse error.
        """
        httpx_mod, bs4_mod = _import_url_deps()
        try:
            html_text = _fetch_final_html(httpx_mod, str(url), max_bytes)
            soup = bs4_mod.BeautifulSoup(html_text, "html.parser")
            return soup.get_text(separator="\n", strip=True)
        except ExtractionError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError(str(exc)) from exc
