"""
Domain Port: ISourceExtractor & SourceType

Decouples Learning services from concrete PDF, URL, Markdown, and Image extractors.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Protocol, runtime_checkable

from src.domain.ports.llm_provider import ILLMProvider


class SourceType(Enum):
    """Supported external knowledge source formats."""

    PDF = "pdf"
    URL = "url"
    MARKDOWN = "markdown"
    IMAGE = "image"
    TEXT = "text"


@runtime_checkable
class ISourceExtractor(Protocol):
    """Port for extracting raw text from external learning sources."""

    def extract(
        self,
        source: str | Path,
        /,
        *,
        llm_provider: ILLMProvider | None = None,
        model_name: str = "",
    ) -> str:
        """Extract raw textual content from ``source``."""
        ...
