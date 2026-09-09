"""
RED tests for ChromaDBDocumentStore.

Spec: obsidian_vault/docs/features/feature_rag_ingestion.md
Phase: 2 | Layer: Infrastructure

Uses chromadb.EphemeralClient() (in-memory, no disk) for fast, isolated tests.
Semantic relevance is tested here — these tests may be slower than unit tests
on first run because sentence-transformers downloads the model (~80MB).
"""
import pytest

from src.domain.value_objects.document_chunk import DocumentChunk, SearchFilter
from src.infrastructure.rag.chroma_document_store import ChromaDBDocumentStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunk(chunk_id: str, content: str, doc_type: str = "spec") -> DocumentChunk:
    return DocumentChunk(
        id=chunk_id,
        content=content,
        file_path=chunk_id.split("#")[0],
        heading=chunk_id.split("#")[1] if "#" in chunk_id else "",
        metadata={"type": doc_type, "phase": "2", "status": "draft"},
        score=None,
    )


# ---------------------------------------------------------------------------
# Fixture: ephemeral (in-memory) ChromaDB store — no disk I/O
# ---------------------------------------------------------------------------

@pytest.fixture()
def chroma_store() -> ChromaDBDocumentStore:
    """
    Returns a ChromaDBDocumentStore backed by an EphemeralClient.
    Each test gets a unique collection name to guarantee isolation —
    EphemeralClient shares state across collections within the same process.
    """
    import uuid
    unique_collection = f"test_{uuid.uuid4().hex}"
    return ChromaDBDocumentStore(ephemeral=True, collection_name=unique_collection)


# ---------------------------------------------------------------------------
# Scenario 1: upsert stores chunks and count reflects them
# ---------------------------------------------------------------------------

def test_upsert_increases_count(chroma_store: ChromaDBDocumentStore) -> None:
    chunk_a = _make_chunk("docs/a.md#overview", "Overview of the system architecture")
    chunk_b = _make_chunk("docs/b.md#voice", "Voice recognition with Whisper STT")

    chroma_store.upsert([chunk_a, chunk_b])

    assert chroma_store.count() == 2


# ---------------------------------------------------------------------------
# Scenario 2: search returns the most semantically relevant chunk
# ---------------------------------------------------------------------------

def test_search_returns_semantically_relevant_chunk(chroma_store: ChromaDBDocumentStore) -> None:
    sqlite_chunk = _make_chunk(
        "infra.md#storage",
        "SQLite is used to persist domain entities such as agents and tasks to disk.",
    )
    voice_chunk = _make_chunk(
        "voice.md#stt",
        "Whisper.cpp is used for local speech-to-text voice recognition.",
    )

    chroma_store.upsert([sqlite_chunk, voice_chunk])
    results = chroma_store.search("how are agents and tasks stored?", top_k=1)

    assert len(results) == 1
    assert results[0].id == sqlite_chunk.id
    assert results[0].score is not None


# ---------------------------------------------------------------------------
# Scenario 3: upsert is idempotent — re-ingesting does not duplicate
# ---------------------------------------------------------------------------

def test_upsert_is_idempotent(chroma_store: ChromaDBDocumentStore) -> None:
    chunk = _make_chunk("docs/spec.md#overview", "Clean architecture overview")
    updated = DocumentChunk(
        id=chunk.id,
        content="Updated clean architecture overview with more detail",
        file_path=chunk.file_path,
        heading=chunk.heading,
        metadata=chunk.metadata,
        score=None,
    )

    chroma_store.upsert([chunk])
    chroma_store.upsert([updated])  # same id — must replace, not duplicate

    assert chroma_store.count() == 1


# ---------------------------------------------------------------------------
# Scenario 4: search with SearchFilter(type="adr") returns only ADR chunks
# ---------------------------------------------------------------------------

def test_search_with_filter_by_type(chroma_store: ChromaDBDocumentStore) -> None:
    spec_chunk = _make_chunk("spec.md#overview", "Clean architecture spec overview", doc_type="spec")
    adr_chunk = _make_chunk("adr.md#decision", "Architecture decision record for SQLite persistence", doc_type="adr")

    chroma_store.upsert([spec_chunk, adr_chunk])
    results = chroma_store.search("architecture", filter=SearchFilter(type="adr"))

    assert len(results) >= 1
    assert all(r.metadata["type"] == "adr" for r in results)


# ---------------------------------------------------------------------------
# Scenario 5: delete removes the specified chunk
# ---------------------------------------------------------------------------

def test_delete_removes_chunk(chroma_store: ChromaDBDocumentStore) -> None:
    chunk = _make_chunk("docs/file.md#intro", "Introduction to the project")

    chroma_store.upsert([chunk])
    assert chroma_store.count() == 1

    chroma_store.delete([chunk.id])

    assert chroma_store.count() == 0
