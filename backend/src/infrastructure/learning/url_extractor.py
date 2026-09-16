"""
Infrastructure Adapter: URLExtractor

Fetches a web page with httpx and extracts clean text using
beautifulsoup4 (html.parser). Both SDKs are imported lazily.
"""
from __future__ import annotations

from src.domain.exceptions import ExtractionError


class URLExtractor:
    """Fetches and strips HTML from a URL, returning plain text."""

    @staticmethod
    def extract(url: str) -> str:
        """
        Fetch ``url`` and return its visible text content.

        Args:
            url: HTTP/HTTPS URL to fetch.

        Returns:
            Plain text extracted from the page body.

        Raises:
            ExtractionError: On network failure, bad HTTP status, or parse error.
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

        try:
            response = httpx.get(url, follow_redirects=True, timeout=30)
            response.raise_for_status()
            soup = bs4.BeautifulSoup(response.text, "html.parser")
            return soup.get_text(separator="\n", strip=True)
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError(str(exc)) from exc
