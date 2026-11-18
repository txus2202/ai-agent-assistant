#!/usr/bin/env python3
"""
ATENEA — Vault Ingestion CLI
=============================
Parses all Markdown files in the Obsidian vault, chunks them by H2/H3
sections, embeds them with sentence-transformers (local, no API key),
and upserts them into ChromaDB.

Usage
-----
    python scripts/ingest_vault.py [OPTIONS]

Options
-------
    --vault-root  PATH   Root directory of the Obsidian vault.
                         Defaults to ./obsidian_vault relative to this script.
    --chroma-path PATH   ChromaDB persist directory.
                         Defaults to CHROMA_PERSIST_DIR (or legacy CHROMA_PATH)
                         env var or ~/.ai-agent-assistant/chroma.
    --chroma-host HOST   ChromaDB HTTP server host (overrides local persistence).
                         Defaults to CHROMA_HOST env var.
    --chroma-port PORT   ChromaDB HTTP server port (default: CHROMA_PORT or 8000).
    --dry-run            Parse and count chunks without writing to ChromaDB.
    --verbose, -v        Print every processed file.
    --help               Show this message and exit.

Environment variables
---------------------
    CHROMA_PERSIST_DIR  Override local ChromaDB storage directory.
    CHROMA_PATH         Legacy alias for CHROMA_PERSIST_DIR.
    CHROMA_HOST         Remote ChromaDB server hostname (e.g. chroma-server).
    CHROMA_PORT         Remote ChromaDB server port (default: 8000).
    RAG_TOP_K           (Used at query time, not here — documented for reference.)

Examples
--------
    # Ingest locally
    python scripts/ingest_vault.py

    # Ingest into external ChromaDB server (--profile scale)
    python scripts/ingest_vault.py --chroma-host 127.0.0.1 --chroma-port 8001

    # Dry-run: see what would be ingested without writing
    python scripts/ingest_vault.py --dry-run --verbose
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Make sure the backend src package is importable when running from project root
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
_BACKEND_SRC = _PROJECT_ROOT / "backend"

if str(_BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(_BACKEND_SRC))

from src.application.services.ingest_vault import IngestVault  # noqa: E402
from src.domain.ports.document_store import IDocumentStore  # noqa: E402
from src.infrastructure.rag.chroma_document_store import ChromaDBDocumentStore  # noqa: E402
from src.infrastructure.rag.in_memory_document_store import InMemoryDocumentStore  # noqa: E402

# ---------------------------------------------------------------------------
# ANSI colour helpers (gracefully degrade on non-TTY)
# ---------------------------------------------------------------------------

_IS_TTY = sys.stdout.isatty()


def _green(text: str) -> str:
    return f"\033[32m{text}\033[0m" if _IS_TTY else text


def _red(text: str) -> str:
    return f"\033[31m{text}\033[0m" if _IS_TTY else text


def _bold(text: str) -> str:
    return f"\033[1m{text}\033[0m" if _IS_TTY else text


# ---------------------------------------------------------------------------
# Argument parsing & store resolution
# ---------------------------------------------------------------------------

def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="ingest_vault",
        description="Ingest the ATENEA Obsidian vault into ChromaDB.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--vault-root",
        type=Path,
        default=_PROJECT_ROOT / "obsidian_vault",
        metavar="PATH",
        help="Root directory of the Obsidian vault (default: ./obsidian_vault).",
    )
    parser.add_argument(
        "--chroma-path",
        type=str,
        default=None,
        metavar="PATH",
        help=(
            "ChromaDB persist directory "
            "(default: CHROMA_PERSIST_DIR or CHROMA_PATH env var, or ~/.ai-agent-assistant/chroma)."
        ),
    )
    parser.add_argument(
        "--chroma-host",
        type=str,
        default=None,
        metavar="HOST",
        help="Remote ChromaDB HTTP server hostname (default: CHROMA_HOST env var).",
    )
    parser.add_argument(
        "--chroma-port",
        type=int,
        default=None,
        metavar="PORT",
        help="Remote ChromaDB HTTP server port (default: CHROMA_PORT env var or 8000).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and count chunks without writing to ChromaDB.",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print every processed file.",
    )
    return parser.parse_args(argv)


def _resolve_document_store(
    *,
    dry_run: bool,
    chroma_path: str | None,
    chroma_host: str | None,
    chroma_port: int | None,
) -> tuple[IDocumentStore, str]:
    if dry_run:
        return InMemoryDocumentStore(), "dry-run (InMemory — nothing written to disk)"

    resolved_host = chroma_host or os.getenv("CHROMA_HOST") or None
    if resolved_host:
        resolved_port = chroma_port if chroma_port is not None else int(os.getenv("CHROMA_PORT", "8000"))
        store = ChromaDBDocumentStore(host=resolved_host, port=resolved_port)
        return store, f"vault_docs  (http: {resolved_host}:{resolved_port})"

    resolved_chroma = (
        chroma_path
        or os.getenv("CHROMA_PERSIST_DIR")
        or os.getenv("CHROMA_PATH")
        or os.path.expanduser("~/.ai-agent-assistant/chroma")
    )
    store = ChromaDBDocumentStore(persist_directory=resolved_chroma)
    return store, f"vault_docs  (persist: {resolved_chroma})"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    vault_root: Path = args.vault_root.resolve()
    dry_run: bool = args.dry_run
    verbose: bool = args.verbose

    # ── Validate vault root ───────────────────────────────────────────────
    if not vault_root.is_dir():
        print(_red(f"✗ Vault root not found: {vault_root}"), file=sys.stderr)
        return 1

    # ── Choose document store ─────────────────────────────────────────────
    store, store_label = _resolve_document_store(
        dry_run=dry_run,
        chroma_path=args.chroma_path,
        chroma_host=args.chroma_host,
        chroma_port=args.chroma_port,
    )

    # ── Verbose callback ──────────────────────────────────────────────────
    def _on_file(file_path: Path, n_chunks: int) -> None:
        rel = file_path.relative_to(vault_root)
        print(f"    {_green('✓')} {rel}  ({n_chunks} chunks)")

    # ── Print header ──────────────────────────────────────────────────────
    print(_bold("\n  ATENEA — Vault Ingestion"))
    print(f"  Vault : {vault_root}")
    print(f"  Store : {store_label}\n")

    # ── Run ingestion ─────────────────────────────────────────────────────
    t0 = time.perf_counter()
    result = IngestVault.run(
        vault_root=vault_root,
        document_store=store,
        on_file=_on_file if verbose else None,
    )
    elapsed = time.perf_counter() - t0

    # ── Summary ───────────────────────────────────────────────────────────
    status_icon = _green("✓") if not result.errors else _red("⚠")
    deleted_info = f" · {_bold(str(result.files_deleted))} orphaned files purged" if result.files_deleted else ""
    print(
        f"\n  {status_icon}  {_bold(str(result.files_processed))} files processed · "
        f"{_bold(str(result.chunks_upserted))} chunks upserted{deleted_info} · "
        f"{_bold(str(len(result.errors)))} errors  "
        f"({elapsed:.2f}s)\n"
    )

    if result.errors:
        print(_red("  Errors:"))
        for err in result.errors:
            print(f"    {_red('•')} {err}")
        print()

    return 1 if result.errors else 0


if __name__ == "__main__":
    sys.exit(main())
