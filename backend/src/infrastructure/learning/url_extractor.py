"""
Infrastructure Adapter: URLExtractor

Fetches a web page with httpx and extracts clean text using
beautifulsoup4 (html.parser), enforcing SSRF protections and download size limits.
"""
from __future__ import annotations

import ipaddress
import socket
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


def _validate_url_target(url: str) -> None:
    """Validate URL scheme, hostname, and resolved DNS IP addresses against SSRF."""
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


class URLExtractor:
    """Fetches and strips HTML from a URL safely, returning plain text."""

    @staticmethod
    def extract(url: str, max_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES) -> str:
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

        current_url = url
        try:
            for _ in range(MAX_REDIRECTS + 1):
                _validate_url_target(current_url)
                response = httpx.get(current_url, follow_redirects=False, timeout=30)

                status_code = getattr(response, "status_code", None)
                if status_code in _REDIRECT_STATUS_CODES:
                    headers = getattr(response, "headers", {})
                    location = headers.get("location") if headers is not None else None
                    if not isinstance(location, str) or not location.strip():
                        raise ExtractionError("Redirect response missing Location header")
                    current_url = urljoin(current_url, location.strip())
                    continue

                headers = getattr(response, "headers", None)
                raw_cl = headers.get("content-length") if headers is not None else None
                if isinstance(raw_cl, (str, int)) and str(raw_cl).strip().isdigit():
                    if int(str(raw_cl).strip()) > max_bytes:
                        raise ExtractionError(
                            f"Response Content-Length exceeds maximum allowed limit ({max_bytes} bytes)"
                        )

                response.raise_for_status()

                raw_content = getattr(response, "content", None)
                if isinstance(raw_content, (bytes, bytearray)) and len(raw_content) > max_bytes:
                    raise ExtractionError(
                        f"Response size exceeds maximum allowed limit ({max_bytes} bytes)"
                    )

                html_text = response.text
                if isinstance(html_text, str) and len(html_text.encode("utf-8", errors="ignore")) > max_bytes:
                    raise ExtractionError(
                        f"Response size exceeds maximum allowed limit ({max_bytes} bytes)"
                    )

                soup = bs4.BeautifulSoup(html_text, "html.parser")
                return soup.get_text(separator="\n", strip=True)

            raise ExtractionError(f"Exceeded maximum number of redirects ({MAX_REDIRECTS})")
        except ExtractionError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError(str(exc)) from exc
