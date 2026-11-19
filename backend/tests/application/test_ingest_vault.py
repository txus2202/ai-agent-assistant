"""
Unit & Integration Tests for IngestVault application service.

Uses InMemoryDocumentStore and tmp_path — no ChromaDB or embeddings needed.
"""
from pathlib import Path

import pytest

from src.application.services.ingest_vault import IngestResult, IngestVault
from src.domain.ports.document_parser import IDocumentParser
from src.infrastructure.rag.in_memory_document_store import InMemoryDocumentStore
from src.infrastructure.rag.obsidian_parser import ObsidianParser


def _write_md(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@pytest.fixture
def store() -> InMemoryDocumentStore:
    return InMemoryDocumentStore()


@pytest.fixture
def parser() -> IDocumentParser:
    return ObsidianParser()


def test_ingest_vault_requires_injected_document_parser(
    tmp_path: Path,
    store: InMemoryDocumentStore,
) -> None:
    with pytest.raises(ValueError, match="document_parser"):
        IngestVault.run(vault_root=tmp_path, document_store=store)


def test_ingest_vault_processes_all_md_files(
    tmp_path: Path,
    store: InMemoryDocumentStore,
    parser: IDocumentParser,
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

    result = IngestVault.run(vault_root=tmp_path, document_store=store, document_parser=parser)

    assert result.files_processed == 3
    assert result.chunks_upserted >= 5
    assert result.errors == []
    assert store.count() == result.chunks_upserted


def test_ingest_vault_skips_obsidian_directory(
    tmp_path: Path,
    store: InMemoryDocumentStore,
    parser: IDocumentParser,
) -> None:
    _write_md(
        tmp_path / "real_note.md",
        "## Note\nThis should be ingested.\n",
    )
    _write_md(
        tmp_path / ".obsidian" / "plugins.md",
        "## Plugin Config\nThis must NOT be ingested.\n",
    )

    result = IngestVault.run(vault_root=tmp_path, document_store=store, document_parser=parser)

    assert result.files_processed == 1
    assert store.count() == 1


def test_ingest_vault_is_idempotent(
    tmp_path: Path,
    store: InMemoryDocumentStore,
    parser: IDocumentParser,
) -> None:
    _write_md(
        tmp_path / "doc.md",
        "## Section A\nContent A.\n## Section B\nContent B.\n",
    )

    IngestVault.run(vault_root=tmp_path, document_store=store, document_parser=parser)
    first_count = store.count()

    IngestVault.run(vault_root=tmp_path, document_store=store, document_parser=parser)
    second_count = store.count()

    assert first_count == second_count


def test_ingest_result_has_expected_fields(
    tmp_path: Path,
    store: InMemoryDocumentStore,
    parser: IDocumentParser,
) -> None:
    _write_md(tmp_path / "note.md", "## Section\nSome content.\n")

    result = IngestVault.run(vault_root=tmp_path, document_store=store, document_parser=parser)

    assert isinstance(result, IngestResult)
    assert isinstance(result.files_processed, int)
    assert isinstance(result.chunks_upserted, int)
    assert isinstance(result.files_deleted, int)
    assert isinstance(result.errors, list)


def test_ingest_vault_cleans_up_orphaned_files(
    tmp_path: Path,
    store: InMemoryDocumentStore,
    parser: IDocumentParser,
) -> None:
    file_a = tmp_path / "note_a.md"
    file_b = tmp_path / "note_b.md"
    _write_md(file_a, "## Section A\nContent of A.\n")
    _write_md(file_b, "## Section B\nContent of B.\n")

    res1 = IngestVault.run(vault_root=tmp_path, document_store=store, document_parser=parser)
    assert res1.files_processed == 2
    assert res1.files_deleted == 0
    assert store.count() == 2

    file_b.unlink()

    res2 = IngestVault.run(vault_root=tmp_path, document_store=store, document_parser=parser)
    assert res2.files_processed == 1
    assert res2.files_deleted == 1
    assert store.count() == 1
    assert store.get_indexed_file_paths() == {"note_a.md"}
