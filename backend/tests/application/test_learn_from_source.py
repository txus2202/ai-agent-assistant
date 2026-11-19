"""
Tests — LearnFromSource Service (Feature: feature_learning_agent.md)

Layer: Application

Strategy:
  - Source extractors and document parser are injected via domain ports (ISourceExtractor, IDocumentParser).
  - LLM provider is a FakeLLMProvider returning deterministic .md content.
  - InMemoryDocumentStore is used — no ChromaDB needed.
  - tmp_path is the vault_root.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from src.application.services.learn_from_source import (
    LearnFromSource,
    SourceType,
    _extract_clean_file_tags,
)
from src.application.services.query_vault import QueryVault
from src.domain.exceptions import ExtractionError, LLMProviderError
from src.domain.ports.llm_provider import ILLMProvider
from src.domain.ports.source_extractor import ISourceExtractor
from src.domain.value_objects.document_chunk import DocumentChunk
from src.infrastructure.rag.in_memory_document_store import InMemoryDocumentStore


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
    def list_models(self, probe: bool = True) -> list[dict[str, str]]:
        return [{"id": "test", "name": "Test"}]

    def complete(self, prompt: str, model_name: str) -> str:
        return _SAMPLE_MD


class FailingLLM(ILLMProvider):
    def list_models(self, probe: bool = True) -> list[dict[str, str]]:
        return [{"id": "test", "name": "Test"}]

    def complete(self, prompt: str, model_name: str) -> str:
        raise LLMProviderError("LLM unavailable")


class StubExtractor(ISourceExtractor):
    def __init__(self, content: str | Exception) -> None:
        self._content = content

    def extract(
        self,
        source: str | Path,
        /,
        *,
        llm_provider: ILLMProvider | None = None,
        model_name: str = "",
    ) -> str:
        if isinstance(self._content, Exception):
            raise self._content
        return self._content


class StubMarkdownExtractor(ISourceExtractor):
    def extract(
        self,
        source: str | Path,
        /,
        *,
        llm_provider: ILLMProvider | None = None,
        model_name: str = "",
    ) -> str:
        return Path(source).read_text(encoding="utf-8")


class SimpleStubParser:
    """Minimal pure IDocumentParser test double splitting sections by H2 headers."""

    def parse(self, file_path: Path, vault_root: Path) -> list[DocumentChunk]:
        text = file_path.read_text(encoding="utf-8")
        rel = file_path.relative_to(vault_root).as_posix()
        chunks: list[DocumentChunk] = []
        sections = text.split("## ")
        for idx, section in enumerate(sections):
            body = section.strip()
            if not body:
                continue
            heading = "" if idx == 0 else body.splitlines()[0].strip()
            chunks.append(
                DocumentChunk(
                    id=f"{rel}#{idx}",
                    content=body,
                    file_path=rel,
                    heading=heading,
                    metadata={},
                    score=None,
                )
            )
        return chunks


def _default_extractors(
    url_text: str = "Some raw content from the web.",
    pdf_text: str = "Some raw content from a PDF.",
    image_text: str = "# Architecture\nComponent A -> B",
) -> dict[SourceType, ISourceExtractor]:
    return {
        SourceType.URL: StubExtractor(url_text),
        SourceType.PDF: StubExtractor(pdf_text),
        SourceType.MARKDOWN: StubMarkdownExtractor(),
        SourceType.IMAGE: StubExtractor(image_text),
    }


class TestLearnFromSource:
    def test_requires_injected_document_parser(self, tmp_path: Path):
        with pytest.raises(ValueError, match="document_parser"):
            LearnFromSource.run(
                source="Raw text",
                source_type=SourceType.TEXT,
                llm_provider=FakeLLM(),
                document_store=InMemoryDocumentStore(),
                vault_root=tmp_path,
            )

    def test_url_source_creates_md_file_in_learned_directory(self, tmp_path: Path):
        store = InMemoryDocumentStore()
        result = LearnFromSource.run(
            source="https://example.com/article",
            source_type=SourceType.URL,
            llm_provider=FakeLLM(),
            document_store=store,
            vault_root=tmp_path,
            extractors=_default_extractors(),
            document_parser=SimpleStubParser(),
        )

        assert result.generated_file is not None
        assert result.generated_file.exists()
        assert result.generated_file.parent.name == "learned"
        assert result.generated_file.suffix == ".md"

    def test_pdf_source_creates_md_file(self, tmp_path: Path):
        store = InMemoryDocumentStore()
        pdf_path = tmp_path / "test.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")

        result = LearnFromSource.run(
            source=str(pdf_path),
            source_type=SourceType.PDF,
            llm_provider=FakeLLM(),
            document_store=store,
            vault_root=tmp_path,
            extractors=_default_extractors(),
            document_parser=SimpleStubParser(),
        )

        assert result.generated_file is not None
        assert result.generated_file.exists()

    def test_generated_md_has_yaml_frontmatter(self, tmp_path: Path):
        result = LearnFromSource.run(
            source="https://example.com",
            source_type=SourceType.URL,
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            vault_root=tmp_path,
            extractors=_default_extractors(),
            document_parser=SimpleStubParser(),
        )

        content = result.generated_file.read_text(encoding="utf-8")
        assert content.startswith("---")

    def test_generated_md_has_at_least_one_h2_section(self, tmp_path: Path):
        result = LearnFromSource.run(
            source="https://example.com",
            source_type=SourceType.URL,
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            vault_root=tmp_path,
            extractors=_default_extractors(),
            document_parser=SimpleStubParser(),
        )

        content = result.generated_file.read_text(encoding="utf-8")
        assert "## " in content

    def test_generated_md_is_ingested_into_store(self, tmp_path: Path):
        """Scenario 3: generated .md is queryable via RAG after run()."""
        store = InMemoryDocumentStore()

        LearnFromSource.run(
            source="https://example.com",
            source_type=SourceType.URL,
            llm_provider=FakeLLM(),
            document_store=store,
            vault_root=tmp_path,
            extractors=_default_extractors(),
            document_parser=SimpleStubParser(),
        )

        results = QueryVault.run(
            query="clean architecture domain infrastructure",
            document_store=store,
        )
        assert len(results) >= 1

    def test_extraction_failure_returns_result_with_errors_not_raises(self, tmp_path: Path):
        """Scenario 6: errors in LearnResult, no exception raised."""
        extractors = _default_extractors()
        extractors[SourceType.PDF] = StubExtractor(ExtractionError("corrupt PDF"))

        result = LearnFromSource.run(
            source="/tmp/bad.pdf",
            source_type=SourceType.PDF,
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            vault_root=tmp_path,
            extractors=extractors,
            document_parser=SimpleStubParser(),
        )

        assert len(result.errors) > 0
        assert result.generated_file is None
        assert "corrupt PDF" in result.errors[0]

    def test_missing_extractor_returns_error_not_raises(self, tmp_path: Path):
        result = LearnFromSource.run(
            source="https://example.com",
            source_type=SourceType.URL,
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            vault_root=tmp_path,
            extractors={},
            document_parser=SimpleStubParser(),
        )

        assert len(result.errors) > 0
        assert result.generated_file is None

    def test_llm_failure_returns_result_with_errors_not_raises(self, tmp_path: Path):
        result = LearnFromSource.run(
            source="https://example.com",
            source_type=SourceType.URL,
            llm_provider=FailingLLM(),
            document_store=InMemoryDocumentStore(),
            vault_root=tmp_path,
            extractors=_default_extractors(),
            document_parser=SimpleStubParser(),
        )

        assert len(result.errors) > 0
        assert result.generated_file is None

    def test_idempotency_same_source_overwrites_file(self, tmp_path: Path):
        """Scenario 7: running twice with same source -> single .md file."""
        store = InMemoryDocumentStore()
        extractors = _default_extractors()
        parser = SimpleStubParser()

        r1 = LearnFromSource.run(
            source="https://example.com/article",
            source_type=SourceType.URL,
            llm_provider=FakeLLM(),
            document_store=store,
            vault_root=tmp_path,
            extractors=extractors,
            document_parser=parser,
        )
        r2 = LearnFromSource.run(
            source="https://example.com/article",
            source_type=SourceType.URL,
            llm_provider=FakeLLM(),
            document_store=store,
            vault_root=tmp_path,
            extractors=extractors,
            document_parser=parser,
        )

        learned_files = list((tmp_path / "learned").glob("*.md"))
        assert len(learned_files) == 1
        assert r1.generated_file == r2.generated_file

    def test_learn_result_has_zero_errors_on_success(self, tmp_path: Path):
        result = LearnFromSource.run(
            source="https://example.com",
            source_type=SourceType.URL,
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            vault_root=tmp_path,
            extractors=_default_extractors(),
            document_parser=SimpleStubParser(),
        )

        assert result.errors == []
        assert result.source == "https://example.com"

    def test_filename_contains_date_prefix(self, tmp_path: Path):
        result = LearnFromSource.run(
            source="https://example.com",
            source_type=SourceType.URL,
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            vault_root=tmp_path,
            extractors=_default_extractors(),
            document_parser=SimpleStubParser(),
        )

        assert re.match(r"\d{4}-\d{2}-\d{2}_", result.generated_file.name)

    def test_learn_from_markdown_source(self, tmp_path: Path):
        md_file = tmp_path / "raw.md"
        md_file.write_text("# Raw notes\nContent", encoding="utf-8")

        result = LearnFromSource.run(
            source=str(md_file),
            source_type=SourceType.MARKDOWN,
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            vault_root=tmp_path,
            extractors=_default_extractors(),
            document_parser=SimpleStubParser(),
        )

        assert result.errors == []
        assert result.generated_file is not None
        assert result.generated_file.exists()

    def test_learn_from_image_source(self, tmp_path: Path):
        img_file = tmp_path / "diag.png"
        img_file.write_bytes(b"fakebytes")

        result = LearnFromSource.run(
            source=str(img_file),
            source_type=SourceType.IMAGE,
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            vault_root=tmp_path,
            extractors=_default_extractors(),
            document_parser=SimpleStubParser(),
        )

        assert result.errors == []
        assert result.generated_file is not None
        assert result.generated_file.exists()

    def test_learn_from_text_source(self, tmp_path: Path):
        result = LearnFromSource.run(
            source="Aprende esto: El patrón CQRS separa comandos de consultas.",
            source_type=SourceType.TEXT,
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            vault_root=tmp_path,
            document_parser=SimpleStubParser(),
        )

        assert result.errors == []
        assert result.generated_file is not None
        assert result.generated_file.exists()

    def test_learn_from_source_includes_filename_in_tags(self, tmp_path: Path):
        md_file = tmp_path / "guia-arquitectura-distribuida.md"
        md_file.write_text("# Guía Técnica\nContenido detallado.", encoding="utf-8")

        result = LearnFromSource.run(
            source=str(md_file),
            source_type=SourceType.MARKDOWN,
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            vault_root=tmp_path,
            extractors=_default_extractors(),
            document_parser=SimpleStubParser(),
        )

        assert result.errors == []
        assert result.generated_file is not None
        content = result.generated_file.read_text(encoding="utf-8")

        assert "guia-arquitectura-distribuida.md" in content
        assert "guia-arquitectura-distribuida" in content

    def test_extract_clean_file_tags_filters_uuid(self):
        uuid_path = Path("/tmp/atenea_uploads/12535bde-9d79-4573-a805-05cd3812847e.jpg")
        assert _extract_clean_file_tags(uuid_path) == []

        prefixed_path = Path("/tmp/atenea_uploads/3a7b1c2d_diagrama_arquitectura.jpg")
        tags = _extract_clean_file_tags(prefixed_path)
        assert "diagrama_arquitectura.jpg" in tags
        assert "diagrama_arquitectura" in tags

    def test_learn_from_source_preserves_inferred_tags_and_user_tags(self, tmp_path: Path):
        result = LearnFromSource.run(
            source="Texto sobre microservicios y mensajería.",
            source_type=SourceType.TEXT,
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            vault_root=tmp_path,
            tags=["#atenea", "proyecto", "tfm"],
            document_parser=SimpleStubParser(),
        )

        assert result.errors == []
        assert result.generated_file is not None
        content = result.generated_file.read_text(encoding="utf-8")

        assert "python" in content
        assert "architecture" in content
        assert "atenea" in content
        assert "proyecto" in content
        assert "tfm" in content

    def test_learn_from_source_preserves_mermaid_diagrams(self, tmp_path: Path):
        class MermaidLLM(ILLMProvider):
            def list_models(self, probe: bool = True) -> list[dict[str, str]]:
                return [{"id": "test", "name": "Test"}]

            def complete(self, prompt: str, model_name: str) -> str:
                assert "mermaid" in prompt.lower()
                return (
                    "---\ntype: note\ntags: [diagram, architecture]\n---\n\n"
                    "# Diagrama de Sistema\n\n"
                    "```mermaid\ngraph TD\n  A[Frontend] --> B[Backend]\n```\n"
                )

        result = LearnFromSource.run(
            source="Arquitectura con Frontend y Backend.",
            source_type=SourceType.TEXT,
            llm_provider=MermaidLLM(),
            document_store=InMemoryDocumentStore(),
            vault_root=tmp_path,
            document_parser=SimpleStubParser(),
        )

        assert result.errors == []
        assert result.generated_file is not None
        content = result.generated_file.read_text(encoding="utf-8")
        assert "```mermaid" in content
        assert "A[Frontend] --> B[Backend]" in content

    def test_learn_from_source_with_custom_target_domain(self, tmp_path: Path):
        class MockLLM(ILLMProvider):
            def list_models(self, probe: bool = True) -> list[dict[str, str]]:
                return [{"id": "test", "name": "Test"}]

            def complete(self, prompt: str, model_name: str) -> str:
                return (
                    "---\ntype: standard\ntags: [api, standard]\n---\n\n"
                    "# Guia de APIs de la Empresa\n\n## Seccion\nContenido"
                )

        result = LearnFromSource.run(
            source="Texto de directrices de APIs.",
            source_type=SourceType.TEXT,
            llm_provider=MockLLM(),
            document_store=InMemoryDocumentStore(),
            vault_root=tmp_path,
            target_domain="01_enterprise_architecture/guidelines",
            document_parser=SimpleStubParser(),
        )

        assert result.errors == []
        assert result.generated_file is not None
        assert "01_enterprise_architecture/guidelines" in str(result.generated_file)
        assert result.generated_file.exists()
        content = result.generated_file.read_text(encoding="utf-8")
        assert "domain: 01_enterprise_architecture/guidelines" in content
