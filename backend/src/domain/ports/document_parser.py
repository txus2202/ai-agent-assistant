"""
Domain Port: IDocumentParser

Decouples Application ingestion services from concrete Markdown/Obsidian parsers.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from src.domain.value_objects.document_chunk import DocumentChunk


@runtime_checkable
class IDocumentParser(Protocol):
    """Port for parsing vault documents into structured DocumentChunk objects."""

    def parse(self, file_path: Path, vault_root: Path) -> list[DocumentChunk]:
        """Parse ``file_path`` relative to ``vault_root`` into DocumentChunk items."""
        ...

