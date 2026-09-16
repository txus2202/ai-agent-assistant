"""
RED Tests — LearnFromSource Service (Feature: feature_learning_agent.md)

Layer: Application

Strategy:
  - Extractors are mocked via monkeypatch at the module level.
  - LLM provider is a FakeLLMProvider returning deterministic .md content.
  - InMemoryDocumentStore is used — no ChromaDB needed.
  - tmp_path is the vault_root.

Scenarios covered:
  1. PDF source generates a valid .md file
  2. URL source generates a valid .md file
  3. Generated .md is immediately queryable via RAG
  6. LearnResult reports errors without raising when extraction fails
  7. Re-learning the same source is idempotent
  + additional edge cases
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.domain.exceptions import ExtractionError, LLMProviderError
from src.domain.ports.llm_provider import ILLMProvider
from src.infrastructure.rag.in_memory_document_store import InMemoryDocumentStore


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

_SAMPLE_MD = """\
---
type: note
created: 2026-09-16
tags: [python, architecture]
source_url: https://example.com/article
---

# Clean Architecture in Python

## Overview
Clean Architecture separates concerns into concentric layers.

## Domain Layer
The domain layer contains business entities and rules.

## Infrastructure Layer
The infrastructure layer adapts external services to domain ports.
"""


class FakeLLM(ILLMProvider):
    def complete(self, prompt: str, model_name: str) -> str:
        return _SAMPLE_MD


class FailingLLM(ILLMProvider):
    def complete(self, prompt: str, model_name: str) -> str:
        raise LLMProviderError("LLM unavailable")


def _mock_url_extractor(monkeypatch, text: str = "Some raw content from the web."):
    """Replace URLExtractor.extract with a mock that returns `text`."""
    from src.application.services import learn_from_source as _mod
    mock_cls = MagicMock()
    mock_cls.extract.return_value = text
    monkeypatch.setattr(_mod, "URLExtractor", mock_cls)
    return mock_cls


def _mock_pdf_extractor(monkeypatch, text: str = "Some raw content from a PDF."):
    """Replace PDFExtractor.extract with a mock that returns `text`."""
    from src.application.services import learn_from_source as _mod
    mock_cls = MagicMock()
    mock_cls.extract.return_value = text
    monkeypatch.setattr(_mod, "PDFExtractor", mock_cls)
    return mock_cls


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLearnFromSource:
    def test_url_source_creates_md_file_in_learned_directory(
        self, tmp_path: Path, monkeypatch
    ):
        from src.application.services.learn_from_source import LearnFromSource, SourceType

        _mock_url_extractor(monkeypatch)
        store = InMemoryDocumentStore()

        result = LearnFromSource.run(
            source="https://example.com/article",
            source_type=SourceType.URL,
            llm_provider=FakeLLM(),
            document_store=store,
            vault_root=tmp_path,
        )

        assert result.generated_file is not None
        assert result.generated_file.exists()
        assert result.generated_file.parent.name == "learned"
        assert result.generated_file.suffix == ".md"

    def test_pdf_source_creates_md_file(self, tmp_path: Path, monkeypatch):
        from src.application.services.learn_from_source import LearnFromSource, SourceType

        _mock_pdf_extractor(monkeypatch)
        store = InMemoryDocumentStore()
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        result = LearnFromSource.run(
            source=str(pdf_path),
            source_type=SourceType.PDF,
            llm_provider=FakeLLM(),
            document_store=store,
            vault_root=tmp_path,
        )

        assert result.generated_file is not None
        assert result.generated_file.exists()

    def test_generated_md_has_yaml_frontmatter(self, tmp_path: Path, monkeypatch):
        from src.application.services.learn_from_source import LearnFromSource, SourceType

        _mock_url_extractor(monkeypatch)
        result = LearnFromSource.run(
            source="https://example.com",
            source_type=SourceType.URL,
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            vault_root=tmp_path,
        )

        content = result.generated_file.read_text(encoding="utf-8")
        assert content.startswith("---")

    def test_generated_md_has_at_least_one_h2_section(self, tmp_path: Path, monkeypatch):
        from src.application.services.learn_from_source import LearnFromSource, SourceType

        _mock_url_extractor(monkeypatch)
        result = LearnFromSource.run(
            source="https://example.com",
            source_type=SourceType.URL,
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            vault_root=tmp_path,
        )

        content = result.generated_file.read_text(encoding="utf-8")
        assert "## " in content

    def test_generated_md_is_ingested_into_store(self, tmp_path: Path, monkeypatch):
        """Scenario 3: generated .md is queryable via RAG after run()."""
        from src.application.services.learn_from_source import LearnFromSource, SourceType
        from src.application.services.query_vault import QueryVault

        _mock_url_extractor(monkeypatch)
        store = InMemoryDocumentStore()

        LearnFromSource.run(
            source="https://example.com",
            source_type=SourceType.URL,
            llm_provider=FakeLLM(),
            document_store=store,
            vault_root=tmp_path,
        )

        results = QueryVault.run(
            query="clean architecture domain infrastructure",
            document_store=store,
        )
        assert len(results) >= 1

    def test_extraction_failure_returns_result_with_errors_not_raises(
        self, tmp_path: Path, monkeypatch
    ):
        """Scenario 6: errors in LearnResult, no exception raised."""
        from src.application.services import learn_from_source as _mod
        from src.application.services.learn_from_source import LearnFromSource, SourceType

        failing_extractor = MagicMock()
        failing_extractor.extract.side_effect = ExtractionError("corrupt PDF")
        monkeypatch.setattr(_mod, "PDFExtractor", failing_extractor)

        result = LearnFromSource.run(
            source="/tmp/bad.pdf",
            source_type=SourceType.PDF,
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            vault_root=tmp_path,
        )

        assert len(result.errors) > 0
        assert result.generated_file is None
        assert "corrupt PDF" in result.errors[0]

    def test_llm_failure_returns_result_with_errors_not_raises(
        self, tmp_path: Path, monkeypatch
    ):
        from src.application.services.learn_from_source import LearnFromSource, SourceType

        _mock_url_extractor(monkeypatch)

        result = LearnFromSource.run(
            source="https://example.com",
            source_type=SourceType.URL,
            llm_provider=FailingLLM(),
            document_store=InMemoryDocumentStore(),
            vault_root=tmp_path,
        )

        assert len(result.errors) > 0
        assert result.generated_file is None

    def test_idempotency_same_source_overwrites_file(self, tmp_path: Path, monkeypatch):
        """Scenario 7: running twice with same source → single .md file."""
        from src.application.services.learn_from_source import LearnFromSource, SourceType

        _mock_url_extractor(monkeypatch)
        store = InMemoryDocumentStore()

        r1 = LearnFromSource.run(
            source="https://example.com/article",
            source_type=SourceType.URL,
            llm_provider=FakeLLM(),
            document_store=store,
            vault_root=tmp_path,
        )
        r2 = LearnFromSource.run(
            source="https://example.com/article",
            source_type=SourceType.URL,
            llm_provider=FakeLLM(),
            document_store=store,
            vault_root=tmp_path,
        )

        learned_files = list((tmp_path / "learned").glob("*.md"))
        assert len(learned_files) == 1
        assert r1.generated_file == r2.generated_file

    def test_learn_result_has_zero_errors_on_success(self, tmp_path: Path, monkeypatch):
        from src.application.services.learn_from_source import LearnFromSource, SourceType

        _mock_url_extractor(monkeypatch)

        result = LearnFromSource.run(
            source="https://example.com",
            source_type=SourceType.URL,
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            vault_root=tmp_path,
        )

        assert result.errors == []
        assert result.source == "https://example.com"

    def test_filename_contains_date_prefix(self, tmp_path: Path, monkeypatch):
        from src.application.services.learn_from_source import LearnFromSource, SourceType
        import re

        _mock_url_extractor(monkeypatch)

        result = LearnFromSource.run(
            source="https://example.com",
            source_type=SourceType.URL,
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            vault_root=tmp_path,
        )

        # Filename must match YYYY-MM-DD_*.md
        assert re.match(r"\d{4}-\d{2}-\d{2}_", result.generated_file.name)
