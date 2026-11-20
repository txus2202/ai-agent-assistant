"""
Infrastructure Adapter: PDFExtractor

Extracts plain text from PDF files using PyMuPDF (fitz).
SDK is imported lazily to allow mocking in tests and to raise
ExtractionError (not ImportError) when the package is missing.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.domain.exceptions import ExtractionError


class PDFExtractor:
    """Extracts text from PDF files via PyMuPDF."""

    @staticmethod
    def extract(path: Path | str, **_kwargs: Any) -> str:
        """
        Read all pages of a PDF and return concatenated plain text.

        Args:
            path: Absolute path to the PDF file.

        Returns:
            Full text content of the PDF.

        Raises:
            ExtractionError: On import failure or any PyMuPDF error.
        """
        try:
            import fitz  # noqa: PLC0415 — lazy import (PyMuPDF)
        except ImportError as exc:
            raise ExtractionError(
                "PyMuPDF is not installed. Run: pip install PyMuPDF"
            ) from exc

        try:
            text_parts: list[str] = []
            with fitz.open(str(path)) as doc:
                for page in doc:
                    text_parts.append(page.get_text())
            return "".join(text_parts)
        except Exception as exc:  # noqa: BLE001
            raise ExtractionError(str(exc)) from exc
