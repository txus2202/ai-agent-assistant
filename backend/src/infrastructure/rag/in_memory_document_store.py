"""
Infrastructure Adapter: InMemoryDocumentStore

Volatile, keyword-matching implementation of IDocumentStore.
Used in unit tests and as a lightweight stand-in when ChromaDB is unavailable.

Search strategy: Jaccard-like overlap between query words and chunk content.
No embeddings — purely lexical. Use ChromaDBDocumentStore for semantic search.
"""
from __future__ import annotations

import os
from typing import Any

from src.domain.ports.document_store import IDocumentStore
from src.domain.value_objects.document_chunk import DocumentChunk, SearchFilter

_DEFAULT_TOP_K = 5


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
        top_k: int | None = None,
        filter: SearchFilter | None = None,
    ) -> list[DocumentChunk]:
        resolved_top_k = top_k if top_k is not None else int(
            os.getenv("RAG_TOP_K", str(_DEFAULT_TOP_K))
        )
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
        for chunk in ranked[:resolved_top_k]:
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

    def delete_by_file_paths(self, file_paths: list[str]) -> None:
        targets = set(file_paths)
        to_delete = [cid for cid, chunk in self._store.items() if chunk.file_path in targets]
        for cid in to_delete:
            self._store.pop(cid, None)

    def get_indexed_file_paths(self) -> set[str]:
        return {chunk.file_path for chunk in self._store.values() if chunk.file_path}

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

        def _match_val(chunk_val: str | None, target: Any) -> bool:
            if target is None:
                return True
            if chunk_val is None:
                return False
            if isinstance(target, (list, tuple)):
                return chunk_val in [str(x) for x in target]
            return chunk_val == str(target)

        if filter.type is not None:
            result = [c for c in result if _match_val(c.metadata.get("type"), filter.type)]
        if filter.layer is not None:
            result = [c for c in result if _match_val(c.metadata.get("layer"), filter.layer)]
        if filter.status is not None:
            result = [c for c in result if _match_val(c.metadata.get("status"), filter.status)]
        if filter.phase is not None:
            result = [c for c in result if _match_val(c.metadata.get("phase"), filter.phase)]
        if getattr(filter, "category", None) is not None:
            result = [c for c in result if _match_val(c.metadata.get("category"), filter.category)]
        if getattr(filter, "domain", None) is not None:
            result = [c for c in result if _match_val(c.metadata.get("domain"), filter.domain)]
        return result
