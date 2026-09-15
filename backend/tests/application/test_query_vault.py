"""
RED Tests — QueryVault Use Case (Feature: feature_query_vault.md)

Layer: Application

Scenarios:
  - Returns ranked chunks for a valid query
  - Raises ValueError for empty/whitespace query
  - Returns empty list when store is empty
  - SearchFilter is forwarded to document store
  - chunks_to_context returns "" for empty list
  - chunks_to_context includes file_path and heading
"""
from __future__ import annotations

import pytest

from src.domain.value_objects.document_chunk import DocumentChunk, SearchFilter
from src.infrastructure.rag.in_memory_document_store import InMemoryDocumentStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _chunk(chunk_id: str, content: str, file_path: str = "doc.md",
           heading: str = "Section", metadata: dict | None = None) -> DocumentChunk:
    return DocumentChunk(
        id=chunk_id,
        content=content,
        file_path=file_path,
        heading=heading,
        metadata=metadata or {},
        score=None,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestQueryVault:
    def test_returns_chunks_for_valid_query(self):
        from src.application.services.query_vault import QueryVault

        store = InMemoryDocumentStore()
        store.upsert([
            _chunk("doc#arch", "clean architecture hexagonal ports adapters"),
            _chunk("doc#test", "unit tests pytest fixtures"),
        ])

        results = QueryVault.run(query="clean architecture", document_store=store)

        assert len(results) >= 1
        assert results[0].id == "doc#arch"

    def test_raises_value_error_for_empty_query(self):
        from src.application.services.query_vault import QueryVault

        store = InMemoryDocumentStore()
        with pytest.raises(ValueError, match="query cannot be empty"):
            QueryVault.run(query="", document_store=store)

    def test_raises_value_error_for_whitespace_query(self):
        from src.application.services.query_vault import QueryVault

        store = InMemoryDocumentStore()
        with pytest.raises(ValueError, match="query cannot be empty"):
            QueryVault.run(query="   ", document_store=store)

    def test_returns_empty_list_when_store_is_empty(self):
        from src.application.services.query_vault import QueryVault

        store = InMemoryDocumentStore()
        results = QueryVault.run(query="any query", document_store=store)

        assert results == []

    def test_search_filter_is_forwarded(self):
        from src.application.services.query_vault import QueryVault

        store = InMemoryDocumentStore()
        store.upsert([
            _chunk("spec#s", "hexagonal architecture spec", metadata={"type": "spec"}),
            _chunk("adr#a", "hexagonal architecture decision", metadata={"type": "adr"}),
        ])

        results = QueryVault.run(
            query="hexagonal architecture",
            document_store=store,
            filter=SearchFilter(type="spec"),
        )

        assert all(c.metadata.get("type") == "spec" for c in results)
        assert len(results) == 1

    def test_top_k_limits_results(self):
        from src.application.services.query_vault import QueryVault

        store = InMemoryDocumentStore()
        store.upsert([
            _chunk(f"doc#{i}", f"architecture pattern {i}") for i in range(10)
        ])

        results = QueryVault.run(query="architecture pattern", document_store=store, top_k=3)

        assert len(results) <= 3


class TestQueryVaultChunksToContext:
    def test_empty_list_returns_empty_string(self):
        from src.application.services.query_vault import QueryVault

        assert QueryVault.chunks_to_context([]) == ""

    def test_context_includes_file_path(self):
        from src.application.services.query_vault import QueryVault

        chunk = _chunk("DECISIONS.md#adr-012", "RAG architecture decision",
                       file_path="DECISIONS.md", heading="ADR 012")
        context = QueryVault.chunks_to_context([chunk])

        assert "DECISIONS.md" in context

    def test_context_includes_heading(self):
        from src.application.services.query_vault import QueryVault

        chunk = _chunk("DECISIONS.md#adr-012", "RAG architecture decision",
                       file_path="DECISIONS.md", heading="ADR 012")
        context = QueryVault.chunks_to_context([chunk])

        assert "ADR 012" in context

    def test_context_includes_chunk_content(self):
        from src.application.services.query_vault import QueryVault

        chunk = _chunk("doc#s", "unique_marker_content_here")
        context = QueryVault.chunks_to_context([chunk])

        assert "unique_marker_content_here" in context

    def test_context_has_delimiters(self):
        from src.application.services.query_vault import QueryVault

        chunk = _chunk("doc#s", "some content")
        context = QueryVault.chunks_to_context([chunk])

        assert "---" in context
