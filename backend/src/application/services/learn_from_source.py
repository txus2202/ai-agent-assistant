"""
Application Service: LearnFromSource

Implements the Learning Agent pipeline:
  1. Extract raw text from an external source (PDF or URL)
  2. Generate a structured Markdown document via LLM
  3. Save the .md to vault_root/learned/{date}_{slug}.md
  4. Ingest the vault into the document store (updates ChromaDB)
  5. Return a LearnResult summary

This service is the bridge between external knowledge sources and the
Obsidian vault / ChromaDB RAG pipeline (ADR-014).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from src.application.services.ingest_vault import IngestResult, IngestVault
from src.domain.exceptions import ExtractionError, LLMProviderError
from src.domain.ports.document_store import IDocumentStore
from src.domain.ports.llm_provider import ILLMProvider
from src.infrastructure.learning.pdf_extractor import PDFExtractor
from src.infrastructure.learning.url_extractor import URLExtractor

# ---------------------------------------------------------------------------
# System prompt sent to the LLM — enforces vault-compatible .md structure
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """\
You are a knowledge structuring assistant. Given raw text extracted from an external source,
generate a well-structured Markdown document strictly following this format:

1. Start with YAML frontmatter (between --- delimiters) containing:
   - type: note
   - created: {date} (today's date, YYYY-MM-DD format)
   - tags: [list, of, relevant, tags]
   - source_url or source_file (the origin of the content)

2. A single H1 title (# Title) that summarises the document in 5-10 words.

3. Between 3 and 8 H2 sections (## Section Name), each covering one major concept.
   H2 sections may contain H3 subsections for detail.

4. All content must be inside sections — no raw lists or paragraphs at the top level.

5. Use concise, factual language. No filler text, no meta-commentary about the document.

Return ONLY the Markdown document. Do not add any extra explanation.
"""


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

class SourceType(Enum):
    PDF = "pdf"
    URL = "url"


@dataclass
class LearnResult:
    """Summary of a single learning run."""

    source: str
    generated_file: Path | None          # None when extraction or LLM failed
    ingest_result: IngestResult = field(default_factory=IngestResult)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class LearnFromSource:
    """Stateless Learning Agent orchestrator."""

    @staticmethod
    def run(
        source: str,
        source_type: SourceType,
        llm_provider: ILLMProvider,
        document_store: IDocumentStore,
        vault_root: Path,
        model_name: str = "gemini-1.5-flash",
    ) -> LearnResult:
        """
        Learn from an external source and update the knowledge vault.

        Args:
            source:         File path (PDF) or URL string to learn from.
            source_type:    SourceType.PDF or SourceType.URL.
            llm_provider:   ILLMProvider used to generate the structured .md.
            document_store: Target store (ChromaDB or InMemory for tests).
            vault_root:     Root of the Obsidian vault.
            model_name:     Model to use for generation.

        Returns:
            LearnResult with path to generated file, ingest summary, and errors.
            Never raises — all failures are captured in LearnResult.errors.
        """
        # ── 1. Extract raw text ───────────────────────────────────────────
        try:
            if source_type == SourceType.PDF:
                raw_text = PDFExtractor.extract(Path(source))
            else:
                raw_text = URLExtractor.extract(source)
        except ExtractionError as exc:
            return LearnResult(source=source, generated_file=None, errors=[str(exc)])

        # ── 2. Generate structured .md via LLM ───────────────────────────
        date_str = datetime.now().strftime("%Y-%m-%d")
        source_field = (
            f"source_file: {source}" if source_type == SourceType.PDF
            else f"source_url: {source}"
        )
        prompt = (
            f"{_SYSTEM_PROMPT.format(date=date_str)}\n\n"
            f"--- Source metadata ---\n{source_field}\n\n"
            f"--- Raw text ---\n{raw_text}"
        )

        try:
            md_content = llm_provider.complete(prompt, model_name)
        except LLMProviderError as exc:
            return LearnResult(source=source, generated_file=None, errors=[str(exc)])

        # ── 3. Derive slug from H1 title ──────────────────────────────────
        slug = _derive_slug(md_content, source)
        filename = f"{date_str}_{slug}.md"

        # ── 4. Save to vault_root/learned/ ───────────────────────────────
        learned_dir = vault_root / "learned"
        learned_dir.mkdir(parents=True, exist_ok=True)
        file_path = learned_dir / filename
        file_path.write_text(md_content, encoding="utf-8")

        # ── 5. Re-ingest vault (idempotent via upsert) ────────────────────
        ingest_result = IngestVault.run(
            vault_root=vault_root,
            document_store=document_store,
        )

        return LearnResult(
            source=source,
            generated_file=file_path,
            ingest_result=ingest_result,
            errors=[],
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _derive_slug(md_content: str, fallback: str) -> str:
    """
    Extract the H1 title from ``md_content`` and convert it to a URL slug.
    Falls back to a slug derived from ``fallback`` (source URL or path).
    """
    match = re.search(r"^#[ \t]+([^ \t\n].*)$", md_content, re.MULTILINE)
    raw = match.group(1).strip() if match else fallback

    # Convert to lowercase slug: letters, digits and hyphens only
    slug = re.sub(r"[^\w\s-]", "", raw.lower())
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:80]  # cap at 80 chars to keep filenames sane
