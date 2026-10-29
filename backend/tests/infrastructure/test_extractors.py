"""
RED Tests — PDFExtractor & URLExtractor (Feature: feature_learning_agent.md)

Layer: Infrastructure

Strategy:
  - PyMuPDF (fitz) and httpx are mocked via sys.modules + monkeypatch.
  - No real HTTP calls or PDF parsing in the test suite.
  - Both extractors are tested for: happy path, SDK exception wrapping,
    and missing SDK.

Scenarios:
  4. PDF extractor raises ExtractionError for corrupt files
  5. URL extractor raises ExtractionError for unreachable URLs
  (+ positive paths)
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.domain.exceptions import ExtractionError


# ===========================================================================
# PDFExtractor
# ===========================================================================

class TestPDFExtractor:
    @pytest.fixture(autouse=True)
    def mock_fitz(self, monkeypatch, tmp_path):
        """Mock fitz (PyMuPDF) and provide a fake PDF path."""
        mock = MagicMock()
        # Simulate a document with 2 pages, each returning some text
        mock_doc = MagicMock()
        mock_doc.__iter__ = lambda s: iter([
            MagicMock(get_text=lambda: "Page one content. "),
            MagicMock(get_text=lambda: "Page two content."),
        ])
        mock_doc.__enter__ = lambda s: mock_doc
        mock_doc.__exit__ = MagicMock(return_value=False)
        mock.open.return_value = mock_doc

        monkeypatch.setitem(sys.modules, "fitz", mock)
        self._mock_fitz = mock
        self._pdf_path = tmp_path / "test.pdf"
        self._pdf_path.write_bytes(b"%PDF-1.4 fake")

    def test_extract_returns_concatenated_text(self):
        from src.infrastructure.learning.pdf_extractor import PDFExtractor

        result = PDFExtractor.extract(self._pdf_path)

        assert isinstance(result, str)
        assert "Page one content" in result
        assert "Page two content" in result

    def test_extract_raises_extraction_error_on_fitz_failure(self):
        from src.infrastructure.learning.pdf_extractor import PDFExtractor

        self._mock_fitz.open.side_effect = RuntimeError("not a PDF")

        with pytest.raises(ExtractionError, match="not a PDF"):
            PDFExtractor.extract(self._pdf_path)

    def test_extract_raises_extraction_error_for_nonexistent_file(self, tmp_path):
        from src.infrastructure.learning.pdf_extractor import PDFExtractor

        self._mock_fitz.open.side_effect = FileNotFoundError("no such file")

        with pytest.raises(ExtractionError):
            PDFExtractor.extract(tmp_path / "missing.pdf")

    def test_missing_sdk_raises_extraction_error(self, monkeypatch):
        """If PyMuPDF is not installed, extract() raises ExtractionError."""
        monkeypatch.delitem(sys.modules, "fitz", raising=False)

        import builtins
        real_import = builtins.__import__

        def _fail_fitz(name, *args, **kwargs):
            if name == "fitz":
                raise ImportError("No module named 'fitz'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _fail_fitz)

        from src.infrastructure.learning import pdf_extractor
        import importlib
        importlib.reload(pdf_extractor)

        with pytest.raises(ExtractionError, match="PyMuPDF"):
            pdf_extractor.PDFExtractor.extract(self._pdf_path)


# ===========================================================================
# URLExtractor
# ===========================================================================

class TestURLExtractor:
    @pytest.fixture(autouse=True)
    def mock_httpx(self, monkeypatch):
        """Mock httpx to avoid real HTTP calls."""
        mock_httpx = MagicMock()
        mock_response = MagicMock()
        mock_response.text = (
            "<html><body><h1>Title</h1>"
            "<p>Main content here.</p>"
            "<nav>Nav garbage</nav>"
            "</body></html>"
        )
        mock_response.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_response

        mock_bs4 = MagicMock()
        # beautifulsoup4: BeautifulSoup(html, "html.parser").get_text()
        mock_soup_instance = MagicMock()
        mock_soup_instance.get_text.return_value = "Title\nMain content here.\nNav garbage"
        mock_bs4.BeautifulSoup.return_value = mock_soup_instance

        monkeypatch.setitem(sys.modules, "httpx", mock_httpx)
        monkeypatch.setitem(sys.modules, "bs4", mock_bs4)
        self._mock_httpx = mock_httpx
        self._mock_bs4 = mock_bs4

    def test_extract_returns_text_from_url(self):
        from src.infrastructure.learning.url_extractor import URLExtractor

        result = URLExtractor.extract("https://example.com/article")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_extract_calls_get_with_url(self):
        from src.infrastructure.learning.url_extractor import URLExtractor

        URLExtractor.extract("https://example.com/article")

        self._mock_httpx.get.assert_called_once()
        call_args = self._mock_httpx.get.call_args
        assert "https://example.com/article" in str(call_args)

    def test_extract_raises_extraction_error_on_http_failure(self):
        from src.infrastructure.learning.url_extractor import URLExtractor

        self._mock_httpx.get.side_effect = RuntimeError("connection refused")

        with pytest.raises(ExtractionError, match="connection refused"):
            URLExtractor.extract("https://unreachable.invalid")

    def test_extract_raises_extraction_error_on_bad_status(self):
        from src.infrastructure.learning.url_extractor import URLExtractor

        self._mock_httpx.get.return_value.raise_for_status.side_effect = RuntimeError("404")

        with pytest.raises(ExtractionError):
            URLExtractor.extract("https://example.com/gone")


# ===========================================================================
# MarkdownExtractor
# ===========================================================================

class TestMarkdownExtractor:
    def test_extract_returns_markdown_text(self, tmp_path):
        from src.infrastructure.learning.markdown_extractor import MarkdownExtractor

        md_file = tmp_path / "architecture.md"
        content = "# System Architecture\n\n## Overview\nThis is a test architecture note."
        md_file.write_text(content, encoding="utf-8")

        result = MarkdownExtractor.extract(md_file)
        assert result == content

    def test_extract_raises_extraction_error_if_file_missing(self, tmp_path):
        from src.infrastructure.learning.markdown_extractor import MarkdownExtractor

        missing_file = tmp_path / "nonexistent.md"
        with pytest.raises(ExtractionError, match="File not found"):
            MarkdownExtractor.extract(missing_file)


# ===========================================================================
# ImageExtractor
# ===========================================================================

class TestImageExtractor:
    def test_extract_calls_llm_and_returns_description(self, tmp_path):
        from src.infrastructure.learning.image_extractor import ImageExtractor

        img_file = tmp_path / "diagram.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\nfakeimagebytes")

        mock_llm = MagicMock()
        mock_llm.complete_image.return_value = "# Diagrama de Arquitectura\n\n## Componentes\n- Web Client\n- API Gateway"

        result = ImageExtractor.extract(img_file, mock_llm, model_name="gemini-2.5-flash")
        assert "Diagrama de Arquitectura" in result
        mock_llm.complete_image.assert_called_once()

    def test_extract_falls_back_to_complete_if_no_complete_image(self, tmp_path):
        from src.infrastructure.learning.image_extractor import ImageExtractor

        img_file = tmp_path / "diagram.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\nfakeimagebytes")

        mock_llm = MagicMock(spec=["complete"])
        mock_llm.complete.return_value = "# Diagrama Textual"

        result = ImageExtractor.extract(img_file, mock_llm, model_name="test-model")
        assert "Diagrama Textual" in result
        mock_llm.complete.assert_called_once()

    def test_extract_raises_extraction_error_if_image_missing(self, tmp_path):
        from src.infrastructure.learning.image_extractor import ImageExtractor

        missing_img = tmp_path / "missing.png"
        mock_llm = MagicMock()

        with pytest.raises(ExtractionError, match="Image file not found"):
            ImageExtractor.extract(missing_img, mock_llm, model_name="test-model")

    def test_extract_raises_extraction_error_on_llm_failure(self, tmp_path):
        from src.infrastructure.learning.image_extractor import ImageExtractor

        img_file = tmp_path / "diagram.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\nfakeimagebytes")

        mock_llm = MagicMock()
        mock_llm.complete_image.side_effect = RuntimeError("Vision API quota exceeded")

        with pytest.raises(ExtractionError, match="Vision API quota exceeded"):
            ImageExtractor.extract(img_file, mock_llm, model_name="test-model")

