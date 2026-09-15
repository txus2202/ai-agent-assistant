"""
Application Service: IngestVault

Orchestrates the full ingestion pipeline:
  1. Discover all ``.md`` files under ``vault_root`` (recursive, excluding .obsidian/).
  2. Parse each file with ``ObsidianParser`` → list[DocumentChunk].
  3. Upsert all chunks into the provided ``IDocumentStore``.
  4. Return an ``IngestResult`` summary.

Usage:
    result = IngestVault.run(vault_root=Path("obsidian_vault"), document_store=store)
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from src.domain.ports.document_store import IDocumentStore
from src.infrastructure.rag.obsidian_parser import ObsidianParser


@dataclass
class IngestResult:
    """Summary of a single ingestion run."""

    files_processed: int = 0
    chunks_upserted: int = 0
    errors: list[str] = field(default_factory=list)


class IngestVault:
    """Stateless ingestion orchestrator."""

    @staticmethod
    def run(
        vault_root: Path,
        document_store: IDocumentStore,
        on_file: Callable[[Path, int], None] | None = None,
    ) -> IngestResult:
        """
        Ingest all Markdown files under ``vault_root`` into ``document_store``.

        Hidden directories (those whose name starts with ``.``, e.g. ``.obsidian``)
        are silently skipped.

        Args:
            vault_root:     Root directory of the Obsidian vault.
            document_store: Target document store (ChromaDB or InMemory).
            on_file:        Optional callback invoked after each file is parsed
                            successfully. Signature: ``(file_path, n_chunks) -> None``.
                            Useful for progress reporting in CLI and other
                            presentation layers — keeps them DRY.

        Returns:
            ``IngestResult`` with counts of files, chunks, and any errors.
        """
        result = IngestResult()
        all_chunks = []

        md_files = sorted(
            f for f in vault_root.rglob("*.md")
            # Skip any path component that is a hidden directory (starts with ".")
            if not any(part.startswith(".") for part in f.relative_to(vault_root).parts)
        )

        for md_file in md_files:
            try:
                chunks = ObsidianParser.parse(md_file, vault_root=vault_root)
                all_chunks.extend(chunks)
                result.files_processed += 1
                if on_file is not None:
                    on_file(md_file, len(chunks))
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"{md_file.relative_to(vault_root)}: {exc}")

        if all_chunks:
            document_store.upsert(all_chunks)
            result.chunks_upserted = len(all_chunks)

        return result
