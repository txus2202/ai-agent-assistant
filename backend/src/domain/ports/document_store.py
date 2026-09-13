"""
Domain Port: IDocumentStore

Abstract interface that decouples Application use cases and the RAG pipeline
from any specific vector database technology (ADR-004, ADR-012).
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.value_objects.document_chunk import DocumentChunk, SearchFilter


class IDocumentStore(ABC):
    """
    Port (output) for vector-based document retrieval.

    Implementations must be idempotent on ``upsert`` — inserting a chunk
    with an existing ``id`` must replace it, not duplicate it.
    """

    @abstractmethod
    def upsert(self, chunks: list[DocumentChunk]) -> None:
        """
        Insert or replace chunks by their ``id``.
        A no-op for an empty list.
        """

    @abstractmethod
    def search(
        self,
        query: str,
        top_k: int | None = None,
        filter: SearchFilter | None = None,
    ) -> list[DocumentChunk]:
        """
        Return the most relevant chunks for ``query``.

        Args:
            query:  Natural language query to embed and search.
            top_k:  Maximum number of results. When ``None``, implementations
                    must read the ``RAG_TOP_K`` environment variable
                    (default: 5).
            filter: Optional metadata filter to narrow results.

        Returned chunks must have ``score`` set (float in [0, 1]).
        Returns an empty list when the store is empty.
        """

    @abstractmethod
    def delete(self, chunk_ids: list[str]) -> None:
        """Remove chunks by id. Idempotent — no error for unknown ids."""

    @abstractmethod
    def count(self) -> int:
        """Return the total number of stored chunks."""
