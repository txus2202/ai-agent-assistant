"""
Unit tests for SearchFilter translation in ChromaDB and InMemory stores (TDD).
Spec: obsidian_vault/docs/features/feature_dynamic_knowledge_domains.md (AC 6)
"""
import pytest
from src.domain.value_objects.document_chunk import SearchFilter, DocumentChunk
from src.infrastructure.rag.chroma_document_store import ChromaDBDocumentStore
from src.infrastructure.rag.in_memory_document_store import InMemoryDocumentStore


def test_build_where_scalar_category():
    f = SearchFilter(category="enterprise")
    where = ChromaDBDocumentStore._build_where(f)
    assert where == {"category": {"$eq": "enterprise"}}


def test_build_where_list_category_translates_to_in():
    f = SearchFilter(category=["enterprise", "external-learning"])
    where = ChromaDBDocumentStore._build_where(f)
    assert where == {"category": {"$in": ["enterprise", "external-learning"]}}


def test_build_where_combined_filters():
    f = SearchFilter(
        category=["enterprise", "external-learning"],
        type="standard",
    )
    where = ChromaDBDocumentStore._build_where(f)
    assert "$and" in where
    assert {"category": {"$in": ["enterprise", "external-learning"]}} in where["$and"]
    assert {"type": {"$eq": "standard"}} in where["$and"]


def test_in_memory_store_filter_with_list_category():
    chunk1 = DocumentChunk(
        id="c1", content="Text 1", file_path="f1.md", heading="",
        metadata={"category": "enterprise", "type": "standard"}, score=None
    )
    chunk2 = DocumentChunk(
        id="c2", content="Text 2", file_path="f2.md", heading="",
        metadata={"category": "external-learning", "type": "note"}, score=None
    )
    chunk3 = DocumentChunk(
        id="c3", content="Text 3", file_path="f3.md", heading="",
        metadata={"category": "meta-project", "type": "spec"}, score=None
    )

    chunks = [chunk1, chunk2, chunk3]

    # Filter by list of categories
    f1 = SearchFilter(category=["enterprise", "external-learning"])
    res1 = InMemoryDocumentStore._apply_filter(chunks, f1)
    assert len(res1) == 2
    assert chunk1 in res1 and chunk2 in res1
    assert chunk3 not in res1

    # Filter by single scalar category
    f2 = SearchFilter(category="enterprise")
    res2 = InMemoryDocumentStore._apply_filter(chunks, f2)
    assert len(res2) == 1
    assert res2[0] == chunk1

