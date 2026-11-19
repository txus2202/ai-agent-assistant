"""
Infrastructure Adapter: MarkdownExtractor

Extracts plain text / Markdown content from local markdown files.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.domain.exceptions import ExtractionError


class MarkdownExtractor:
    """Extracts text content from Markdown (.md) files."""

    @staticmethod
    def extract(path: Path | str, **_kwargs: Any) -> str:
        """
        Read a Markdown file and return its textual content.

        Args:
            path: Absolute path to the Markdown file.

        Returns:
            Text content of the Markdown file.

        Raises:
            ExtractionError: If the file does not exist or cannot be read.
        """
        p = Path(path)
        if not p.exists() or not p.is_file():
            raise ExtractionError(f"File not found: {path}")

        try:
            return p.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError(f"Failed to read markdown file: {exc}") from exc
