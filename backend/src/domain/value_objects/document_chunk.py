"""
Domain Value Objects: DocumentChunk and SearchFilter

Immutable value objects for the RAG pipeline (ADR-012).
No domain entity dependencies — usable across all layers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SearchFilter:
    """
    Optional filter to narrow vector-store retrieval by metadata fields.

    All fields are optional; only non-None fields are applied as constraints.
    ``phase`` is compared against the string representation stored in metadata
    (ChromaDB requires all metadata values to be strings).
    """

    type: str | None = None      # e.g. "spec", "adr", "note"
    phase: int | None = None     # e.g. 2 → compared as "2" in metadata
    layer: str | None = None     # e.g. "domain", "infrastructure"
    status: str | None = None    # e.g. "implemented", "draft"


@dataclass(frozen=True)
class DocumentChunk:
    """
    Immutable unit of knowledge retrieved from the vector store.

    Identified by ``id`` (``file_path#heading-slug``).
    ``metadata`` stores YAML frontmatter fields as strings (ChromaDB requirement).
    ``score`` is ``None`` when the chunk comes from an upsert context
    (no query score assigned yet) and a float in [0, 1] when returned
    from a similarity search (1.0 = identical, 0.0 = completely different).

    Note on hashability: ``metadata`` is a ``dict`` (not hashable by default).
    ``__hash__`` and ``__eq__`` are therefore defined on ``id`` alone, treating
    the chunk as a value object with identity equal to its unique chunk ID.
    """

    id: str                      # "{file_path}#{heading-slug}"
    content: str                 # raw text of the section
    file_path: str               # relative path within the vault
    heading: str                 # H2/H3 heading text ("" for intro blocks)
    metadata: dict[str, str]     # YAML frontmatter fields, all values as str
    score: float | None          # similarity score from vector search

    # ------------------------------------------------------------------
    # Custom hash/eq — needed because metadata (dict) is not hashable
    # ------------------------------------------------------------------

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DocumentChunk):
            return NotImplemented
        return self.id == other.id
