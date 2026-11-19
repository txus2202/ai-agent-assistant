"""
Tests for the ingest_vault CLI script (scripts/ingest_vault.py).

Layer: Presentation (E2E CLI tests)

These tests run the CLI as a subprocess — they test the full surface that a
user interacts with: exit codes, stdout output, and basic argument handling.

All tests use --dry-run to avoid needing ChromaDB (fast, no disk writes).
Semantic/persistence tests are covered in tests/infrastructure/test_chroma_document_store.py
and tests/application/test_ingest_vault.py.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# Path to the CLI script, relative to the project root
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_CLI = str(_PROJECT_ROOT / "scripts" / "ingest_vault.py")
_REAL_VAULT = str(_PROJECT_ROOT / "obsidian_vault")


def _run(*args: str) -> subprocess.CompletedProcess:
    """Helper: run the CLI with the given args and capture output."""
    return subprocess.run(
        [sys.executable, _CLI, *args],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Scenario 1: --help exits 0 and prints usage
# ---------------------------------------------------------------------------

def test_help_exits_zero_and_shows_usage() -> None:
    result = _run("--help")

    assert result.returncode == 0
    assert "ingest_vault" in result.stdout
    assert "--vault-root" in result.stdout
    assert "--dry-run" in result.stdout


# ---------------------------------------------------------------------------
# Scenario 2: --dry-run with a valid vault exits 0
# ---------------------------------------------------------------------------

def test_dry_run_exits_zero_with_valid_vault(tmp_path: Path) -> None:
    md = tmp_path / "note.md"
    md.write_text("## Overview\nSome content.\n", encoding="utf-8")

    result = _run("--vault-root", str(tmp_path), "--dry-run")

    assert result.returncode == 0
    assert "files processed" in result.stdout


# ---------------------------------------------------------------------------
# Scenario 3: --dry-run --verbose prints each file
# ---------------------------------------------------------------------------

def test_dry_run_verbose_prints_each_file(tmp_path: Path) -> None:
    (tmp_path / "note_a.md").write_text("## Section\nContent.\n", encoding="utf-8")
    (tmp_path / "note_b.md").write_text("## Section\nContent.\n", encoding="utf-8")

    result = _run("--vault-root", str(tmp_path), "--dry-run", "--verbose")

    assert result.returncode == 0
    assert "note_a.md" in result.stdout
    assert "note_b.md" in result.stdout


# ---------------------------------------------------------------------------
# Scenario 4: non-existent vault root exits 1 and prints error to stderr
# ---------------------------------------------------------------------------

def test_invalid_vault_root_exits_one() -> None:
    result = _run("--vault-root", "/tmp/this_does_not_exist_atenea", "--dry-run")

    assert result.returncode == 1
    assert "not found" in result.stderr


# ---------------------------------------------------------------------------
# Scenario 5: .obsidian/ directory is skipped (output does NOT mention it)
# ---------------------------------------------------------------------------

def test_dry_run_skips_obsidian_directory(tmp_path: Path) -> None:
    obsidian_dir = tmp_path / ".obsidian"
    obsidian_dir.mkdir()
    (obsidian_dir / "config.md").write_text("## Config\nPlugin config.\n", encoding="utf-8")
    (tmp_path / "real_note.md").write_text("## Note\nContent.\n", encoding="utf-8")

    result = _run("--vault-root", str(tmp_path), "--dry-run", "--verbose")

    assert result.returncode == 0
    assert "config.md" not in result.stdout
    assert "real_note.md" in result.stdout


# ---------------------------------------------------------------------------
# Scenario 6: summary line shows correct file and chunk counts
# ---------------------------------------------------------------------------

def test_summary_line_shows_correct_counts(tmp_path: Path) -> None:
    # 1 file with 2 non-empty H2 sections → 2 chunks
    md = tmp_path / "doc.md"
    md.write_text(
        "## Section One\nContent one.\n## Section Two\nContent two.\n",
        encoding="utf-8",
    )

    result = _run("--vault-root", str(tmp_path), "--dry-run")

    assert result.returncode == 0
    assert "1" in result.stdout   # 1 file processed
    assert "2" in result.stdout   # 2 chunks upserted
    assert "0 errors" in result.stdout


# ---------------------------------------------------------------------------
# Scenario 7: on_file callback fires for each file (integration with service)
# ---------------------------------------------------------------------------

def test_verbose_output_matches_file_count(tmp_path: Path) -> None:
    """Each processed file must appear exactly once in verbose output."""
    for i in range(3):
        (tmp_path / f"file_{i}.md").write_text(f"## S\nContent {i}.\n", encoding="utf-8")

    result = _run("--vault-root", str(tmp_path), "--dry-run", "--verbose")

    assert result.returncode == 0
    # Each file name must appear in stdout
    for i in range(3):
        assert f"file_{i}.md" in result.stdout


def test_help_shows_chroma_host_and_port_flags() -> None:
    result = _run("--help")

    assert result.returncode == 0
    assert "--chroma-host" in result.stdout
    assert "--chroma-port" in result.stdout
    assert "CHROMA_PERSIST_DIR" in result.stdout


def test_resolve_document_store_supports_http_server_and_chroma_persist_dir(monkeypatch, tmp_path: Path) -> None:
    import importlib.util
    from unittest.mock import MagicMock

    spec = importlib.util.spec_from_file_location("ingest_vault_cli", _CLI)
    assert spec is not None
    assert spec.loader is not None
    cli_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli_mod)

    mock_store_cls = MagicMock()
    monkeypatch.setattr(cli_mod, "ChromaDBDocumentStore", mock_store_cls)

    monkeypatch.setenv("CHROMA_HOST", "chroma-server")
    monkeypatch.setenv("CHROMA_PORT", "8001")
    _, label_http = cli_mod._resolve_document_store(
        dry_run=False, chroma_path=None, chroma_host=None, chroma_port=None
    )
    mock_store_cls.assert_called_once_with(host="chroma-server", port=8001)
    assert "http: chroma-server:8001" in label_http

    mock_store_cls.reset_mock()
    monkeypatch.delenv("CHROMA_HOST", raising=False)
    monkeypatch.setenv("CHROMA_PERSIST_DIR", str(tmp_path / "canonical_chroma"))
    monkeypatch.setenv("CHROMA_PATH", str(tmp_path / "legacy_chroma"))
    _, label_persist = cli_mod._resolve_document_store(
        dry_run=False, chroma_path=None, chroma_host=None, chroma_port=None
    )
    mock_store_cls.assert_called_once_with(persist_directory=str(tmp_path / "canonical_chroma"))
    assert "canonical_chroma" in label_persist
