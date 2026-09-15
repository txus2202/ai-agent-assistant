"""
RED tests for IngestVault application service.

Spec: obsidian_vault/docs/features/feature_rag_ingestion.md (Scenarios 6-8)
Phase: 2 | Layer: Application

Uses InMemoryDocumentStore and tmp_path — no ChromaDB or embeddings needed.
"""
from pathlib import Path

import pytest

from src.application.services.ingest_vault import IngestResult, IngestVault
from src.infrastructure.rag.in_memory_document_store import InMemoryDocumentStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def store() -> InMemoryDocumentStore:
    return InMemoryDocumentStore()


# ---------------------------------------------------------------------------
# Scenario 6: IngestVault processes all .md files in the vault
# ---------------------------------------------------------------------------

def test_ingest_vault_processes_all_md_files(
    tmp_path: Path,
    store: InMemoryDocumentStore,
) -> None:
    _write_md(
        tmp_path / "docs" / "features" / "feature_a.md",
        "---\ntype: spec\n---\n## Section One\nContent one.\n## Section Two\nContent two.\n",
    )
    _write_md(
        tmp_path / "docs" / "features" / "feature_b.md",
        "## Only Section\nContent B.\n",
    )
    _write_md(
        tmp_path / "DECISIONS.md",
        "## ADR 001\nFirst decision.\n## ADR 002\nSecond decision.\n",
    )

    result = IngestVault.run(vault_root=tmp_path, document_store=store)

    assert result.files_processed == 3
    assert result.chunks_upserted >= 5  # at least 5 non-empty sections
    assert result.errors == []
    assert store.count() == result.chunks_upserted


# ---------------------------------------------------------------------------
# Scenario 7: IngestVault skips .obsidian/ directory
# ---------------------------------------------------------------------------

def test_ingest_vault_skips_obsidian_directory(
    tmp_path: Path,
    store: InMemoryDocumentStore,
) -> None:
    _write_md(
        tmp_path / "real_note.md",
        "## Note\nThis should be ingested.\n",
    )
    _write_md(
        tmp_path / ".obsidian" / "plugins.md",
        "## Plugin Config\nThis must NOT be ingested.\n",
    )

    result = IngestVault.run(vault_root=tmp_path, document_store=store)

    assert result.files_processed == 1
    assert store.count() == 1


# ---------------------------------------------------------------------------
# Scenario 8: IngestVault is idempotent — running twice does not duplicate
# ---------------------------------------------------------------------------

def test_ingest_vault_is_idempotent(
    tmp_path: Path,
    store: InMemoryDocumentStore,
) -> None:
    _write_md(
        tmp_path / "doc.md",
        "## Section A\nContent A.\n## Section B\nContent B.\n",
    )

    IngestVault.run(vault_root=tmp_path, document_store=store)
    first_count = store.count()

    IngestVault.run(vault_root=tmp_path, document_store=store)
    second_count = store.count()

    assert first_count == second_count  # re-ingestion must not duplicate


# ---------------------------------------------------------------------------
# Extra: IngestResult is a structured dataclass
# ---------------------------------------------------------------------------

def test_ingest_result_has_expected_fields(
    tmp_path: Path,
    store: InMemoryDocumentStore,
) -> None:
    _write_md(tmp_path / "note.md", "## Section\nSome content.\n")

    result = IngestVault.run(vault_root=tmp_path, document_store=store)

    assert isinstance(result, IngestResult)
    assert isinstance(result.files_processed, int)
    assert isinstance(result.chunks_upserted, int)
    assert isinstance(result.errors, list)
