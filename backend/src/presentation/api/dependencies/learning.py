"""
Composition Root Dependencies: Learning Source Extractors

Wires concrete PDF, URL, Markdown, and Image extractors behind the domain
ISourceExtractor port.
"""
from __future__ import annotations

from starlette.requests import HTTPConnection

from src.domain.ports.source_extractor import ISourceExtractor, SourceType
from src.infrastructure.learning.image_extractor import ImageExtractor
from src.infrastructure.learning.markdown_extractor import MarkdownExtractor
from src.infrastructure.learning.pdf_extractor import PDFExtractor
from src.infrastructure.learning.url_extractor import URLExtractor


def build_source_extractors() -> dict[SourceType, ISourceExtractor]:
    """Build the canonical mapping of SourceType to ISourceExtractor adapters."""
    return {
        SourceType.PDF: PDFExtractor(),
        SourceType.URL: URLExtractor(),
        SourceType.MARKDOWN: MarkdownExtractor(),
        SourceType.IMAGE: ImageExtractor(),
    }


def get_source_extractors(connection: HTTPConnection) -> dict[SourceType, ISourceExtractor]:
    """FastAPI dependency resolving SourceType -> ISourceExtractor mapping from app.state."""
    app_state = getattr(getattr(connection, "app", None), "state", None)
    existing = getattr(app_state, "source_extractors", None) if app_state is not None else None
    if existing is not None:
        return existing
    extractors = build_source_extractors()
    if app_state is not None:
        app_state.source_extractors = extractors
    return extractors

