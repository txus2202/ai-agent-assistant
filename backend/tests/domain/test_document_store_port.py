"""
RED tests for the IDocumentStore domain port and InMemoryDocumentStore.

Spec: obsidian_vault/docs/features/feature_document_store_port.md
Phase: 2 | Layer: Domain
"""
import pytest

from src.domain.ports.document_store import IDocumentStore
from src.domain.value_objects.document_chunk import DocumentChunk, SearchFilter
from src.infrastructure.rag.in_memory_document_store import InMemoryDocumentStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunk(
    file_path: str,
    heading: str,
    content: str,
    doc_type: str = "spec",
) -> DocumentChunk:
    return DocumentChunk(
        id=f"{file_path}#{heading.lower().replace(' ', '-')}",
        content=content,
        file_path=file_path,
        heading=heading,
        metadata={"type": doc_type, "phase": "2", "status": "draft"},
        score=None,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def store() -> InMemoryDocumentStore:
    return InMemoryDocumentStore()


# ---------------------------------------------------------------------------
# Scenario 1: Port is abstract
# ---------------------------------------------------------------------------

def test_document_store_port_is_abstract() -> None:
    with pytest.raises(TypeError):
        IDocumentStore()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# Scenario 2: upsert + search returns semantically relevant chunk
# (InMemoryDocumentStore uses keyword matching, not embeddings)
# ---------------------------------------------------------------------------

def test_search_returns_relevant_chunk_by_keyword(store: InMemoryDocumentStore) -> None:
    sqlite_chunk = _make_chunk("infra.md", "Storage", "sqlite persistence for domain entities database")
    voice_chunk = _make_chunk("voice.md", "Voice", "whisper voice recognition speech to text")

    store.upsert([sqlite_chunk, voice_chunk])
    results = store.search("sqlite database storage", top_k=1)

    assert len(results) >= 1
    assert results[0].id == sqlite_chunk.id


# ---------------------------------------------------------------------------
# Scenario 3: search with SearchFilter narrows results by type
# ---------------------------------------------------------------------------

def test_search_with_filter_returns_only_matching_type(store: InMemoryDocumentStore) -> None:
    spec_chunk = _make_chunk("spec.md", "Overview", "architecture overview", doc_type="spec")
    adr_chunk = _make_chunk("adr.md", "Decision", "architecture decision record", doc_type="adr")

    store.upsert([spec_chunk, adr_chunk])
    results = store.search("architecture", filter=SearchFilter(type="adr"))

    assert len(results) == 1
    assert results[0].metadata["type"] == "adr"


# ---------------------------------------------------------------------------
# Scenario 4: upsert is idempotent — same id does not create a duplicate
# ---------------------------------------------------------------------------

def test_upsert_is_idempotent(store: InMemoryDocumentStore) -> None:
    chunk = _make_chunk("file.md", "Overview", "original content")
    updated_chunk = DocumentChunk(
        id=chunk.id,
        content="updated content",
        file_path=chunk.file_path,
        heading=chunk.heading,
        metadata=chunk.metadata,
        score=None,
    )

    store.upsert([chunk])
    store.upsert([updated_chunk])  # re-upsert same id

    assert store.count() == 1
    found = store.search("updated content", top_k=1)
    assert found[0].content == "updated content"


# ---------------------------------------------------------------------------
# Scenario 5: delete removes chunks
# ---------------------------------------------------------------------------

def test_delete_removes_chunk(store: InMemoryDocumentStore) -> None:
    chunk_a = _make_chunk("a.md", "Intro", "intro content")
    chunk_b = _make_chunk("b.md", "Details", "detail content")

    store.upsert([chunk_a, chunk_b])
    store.delete([chunk_a.id])

    assert store.count() == 1
    results = store.search("intro", top_k=5)
    assert all(r.id != chunk_a.id for r in results)


# ---------------------------------------------------------------------------
# Extra: count reflects number of chunks stored
# ---------------------------------------------------------------------------

def test_count_reflects_stored_chunks(store: InMemoryDocumentStore) -> None:
    assert store.count() == 0
    store.upsert([_make_chunk("x.md", "S1", "content 1")])
    assert store.count() == 1
    store.upsert([_make_chunk("x.md", "S2", "content 2")])
    assert store.count() == 2


# ---------------------------------------------------------------------------
# Extra: search returns at most top_k results
# ---------------------------------------------------------------------------

def test_search_respects_top_k(store: InMemoryDocumentStore) -> None:
    for i in range(5):
        store.upsert([_make_chunk(f"f{i}.md", "Sec", f"architecture content item {i}")])

    results = store.search("architecture", top_k=3)
    assert len(results) <= 3


# ---------------------------------------------------------------------------
# Extra: DocumentChunk is immutable (frozen dataclass)
# ---------------------------------------------------------------------------

def test_document_chunk_is_immutable() -> None:
    chunk = _make_chunk("f.md", "S", "content")
    with pytest.raises((AttributeError, TypeError)):
        chunk.content = "mutated"  # type: ignore[misc]
