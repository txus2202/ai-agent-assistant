"""
Infrastructure Adapter: InMemoryDocumentStore

Volatile, keyword-matching implementation of IDocumentStore.
Used in unit tests and as a lightweight stand-in when ChromaDB is unavailable.

Search strategy: Jaccard-like overlap between query words and chunk content.
No embeddings — purely lexical. Use ChromaDBDocumentStore for semantic search.
"""
from __future__ import annotations

from src.domain.ports.document_store import IDocumentStore
from src.domain.value_objects.document_chunk import DocumentChunk, SearchFilter


class InMemoryDocumentStore(IDocumentStore):
    """
    In-memory implementation of ``IDocumentStore``.

    ``search`` uses word-overlap scoring (not semantic similarity).
    This makes it suitable for deterministic unit tests with carefully
    chosen query words, but not for production use.
    """

    def __init__(self) -> None:
        self._store: dict[str, DocumentChunk] = {}

    def upsert(self, chunks: list[DocumentChunk]) -> None:
        for chunk in chunks:
            self._store[chunk.id] = chunk

    def search(
        self,
        query: str,
        top_k: int = 5,
        filter: SearchFilter | None = None,
    ) -> list[DocumentChunk]:
        candidates = list(self._store.values())

        if filter is not None:
            candidates = self._apply_filter(candidates, filter)

        query_words = set(query.lower().split())

        def _overlap_score(chunk: DocumentChunk) -> float:
            content_words = set(chunk.content.lower().split())
            if not query_words:
                return 0.0
            return len(query_words & content_words) / len(query_words)

        ranked = sorted(candidates, key=_overlap_score, reverse=True)

        results: list[DocumentChunk] = []
        for chunk in ranked[:top_k]:
            score = _overlap_score(chunk)
            results.append(
                DocumentChunk(
                    id=chunk.id,
                    content=chunk.content,
                    file_path=chunk.file_path,
                    heading=chunk.heading,
                    metadata=chunk.metadata,
                    score=score if score > 0 else None,
                )
            )
        return results

    def delete(self, chunk_ids: list[str]) -> None:
        for chunk_id in chunk_ids:
            self._store.pop(chunk_id, None)

    def count(self) -> int:
        return len(self._store)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_filter(
        chunks: list[DocumentChunk],
        filter: SearchFilter,
    ) -> list[DocumentChunk]:
        result = chunks
        if filter.type is not None:
            result = [c for c in result if c.metadata.get("type") == filter.type]
        if filter.layer is not None:
            result = [c for c in result if c.metadata.get("layer") == filter.layer]
        if filter.status is not None:
            result = [c for c in result if c.metadata.get("status") == filter.status]
        if filter.phase is not None:
            result = [c for c in result if c.metadata.get("phase") == str(filter.phase)]
        return result
