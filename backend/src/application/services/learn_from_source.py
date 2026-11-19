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
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from src.application.services.ingest_vault import IngestResult, IngestVault
from src.domain.exceptions import ExtractionError, LLMProviderError
from src.domain.ports.document_parser import IDocumentParser
from src.domain.ports.document_store import IDocumentStore
from src.domain.ports.llm_provider import ILLMProvider
from src.domain.ports.source_extractor import ISourceExtractor, SourceType

# ---------------------------------------------------------------------------
# System prompt sent to the LLM — enforces vault-compatible .md structure
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """\
You are a knowledge structuring assistant. Given raw text extracted from an external source,
generate a well-structured Markdown document strictly following this format:

1. Start with YAML frontmatter (between --- delimiters) containing:
   - type: note
   - created: {date} (today's date, YYYY-MM-DD format)
   - tags: A comprehensive YAML list of 5 to 10 relevant tags. You MUST automatically infer and generate meaningful domain and technical tags from the content (e.g. key concepts, architecture patterns, technologies, protocols). {mandatory_tags_clause}
   - source_url or source_file (the origin of the content)

2. A single H1 title (# Title) that summarises the document in 5-10 words.

3. Between 3 and 8 H2 sections (## Section Name), each covering one major concept.
   H2 sections may contain H3 subsections for detail.

4. All content must be inside sections — no raw lists or paragraphs at the top level.

5. Use concise, factual language. No filler text, no meta-commentary about the document.

6. Diagram Preservation: If the raw text contains Mermaid diagram code blocks (```mermaid ... ```) or visual architecture schemas, you MUST preserve the complete Mermaid diagram block intact within a dedicated section (e.g. ## Diagrama de Arquitectura / Flujo) so the visual representation is persisted and can be rendered.

Return ONLY the Markdown document. Do not add any extra explanation.
"""


# ---------------------------------------------------------------------------
# Public types (SourceType re-exported from domain.ports.source_extractor)
# ---------------------------------------------------------------------------


@dataclass
class LearnResult:
    """Summary of a single learning run."""

    source: str
    generated_file: Path | None          # None when extraction or LLM failed
    ingest_result: IngestResult = field(default_factory=IngestResult)
    errors: list[str] = field(default_factory=list)


def _extract_raw_text(
    source: str,
    source_type: SourceType,
    llm_provider: ILLMProvider,
    model_name: str,
    extractors: Mapping[SourceType, ISourceExtractor] | None = None,
) -> str:
    if source_type == SourceType.TEXT:
        return source
    if not extractors or source_type not in extractors:
        raise ExtractionError(f"Unsupported or unconfigured source type: {source_type}")
    return extractors[source_type].extract(
        source,
        llm_provider=llm_provider,
        model_name=model_name,
    )


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
        model_name: str = "gemini-3.6-flash",
        tags: list[str] | None = None,
        target_domain: str = "learned",
        extractors: Mapping[SourceType, ISourceExtractor] | None = None,
        document_parser: IDocumentParser | None = None,
    ) -> LearnResult:
        """
        Learn from an external source and update the knowledge vault.

        Args:
            source:          File path (PDF, MD, Image), URL or direct text.
            source_type:     SourceType (PDF, URL, MARKDOWN, IMAGE, TEXT).
            llm_provider:    ILLMProvider used to generate the structured .md.
            document_store:  Target store (ChromaDB or InMemory for tests).
            vault_root:      Root of the Obsidian vault.
            model_name:      Model to use for generation.
            tags:            Optional list of explicit tags requested by the user.
            target_domain:   Target domain or directory within the vault (default: 'learned').
            extractors:      Mapping of SourceType -> ISourceExtractor injected from composition root.
            document_parser: Injected IDocumentParser for re-ingesting the updated vault.

        Returns:
            LearnResult with path to generated file, ingest summary, and errors.
            Never raises — all failures are captured in LearnResult.errors.
        """
        if document_parser is None:
            raise ValueError("document_parser must be provided to LearnFromSource.run()")

        # ── 1. Extract raw text ───────────────────────────────────────────
        try:
            raw_text = _extract_raw_text(
                source,
                source_type,
                llm_provider,
                model_name,
                extractors=extractors,
            )
        except ExtractionError as exc:
            return LearnResult(source=source, generated_file=None, errors=[str(exc)])

        # ── 2. Generate structured .md via LLM ───────────────────────────
        date_str = datetime.now().strftime("%Y-%m-%d")
        tags_to_ensure, mandatory_clause = _prepare_tags_and_clause(tags, source, source_type)

        if source_type in (SourceType.PDF, SourceType.MARKDOWN, SourceType.IMAGE):
            source_field = f"source_file: {source}"
        elif source_type == SourceType.URL:
            source_field = f"source_url: {source}"
        else:
            source_field = "source: direct_dialogue"

        prompt = (
            f"{_SYSTEM_PROMPT.format(date=date_str, mandatory_tags_clause=mandatory_clause)}\n\n"
            f"--- Source metadata ---\n{source_field}\n\n"
            f"--- Raw text ---\n{raw_text}"
        )

        try:
            md_content = llm_provider.complete(prompt, model_name)
        except LLMProviderError as exc:
            return LearnResult(source=source, generated_file=None, errors=[str(exc)])

        if tags_to_ensure:
            md_content = _inject_source_tags(md_content, tags_to_ensure)

        # ── 3. Derive slug from H1 title ──────────────────────────────────
        slug = _derive_slug(md_content, source)
        filename = f"{date_str}_{slug}.md"

        # ── 4. Save to vault_root / target_domain ─────────────────────────
        clean_domain = target_domain.strip().strip("/") if target_domain else "learned"
        if ".." in clean_domain:
            clean_domain = "learned"
        dest_dir = vault_root / clean_domain
        dest_dir.mkdir(parents=True, exist_ok=True)
        file_path = dest_dir / filename

        md_content = _inject_domain_metadata(md_content, clean_domain)
        file_path.write_text(md_content, encoding="utf-8")

        # ── 5. Re-ingest vault (idempotent via upsert) ────────────────────
        ingest_result = IngestVault.run(
            vault_root=vault_root,
            document_store=document_store,
            document_parser=document_parser,
        )

        return LearnResult(
            source=source,
            generated_file=file_path,
            ingest_result=ingest_result,
            errors=[],
        )


def _extract_clean_file_tags(file_p: Path) -> list[str]:
    """
    Extract meaningful filename and stem tags from a file path.
    Filters out raw UUIDs and strips random hex prefixes (e.g. 'a1b2c3d4_').
    """
    stem = file_p.stem
    uuid_pattern = r"^[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}$"
    if re.match(uuid_pattern, stem):
        return []

    prefix_match = re.match(r"^[0-9a-fA-F]{8}_(.+)$", stem)
    clean_stem = prefix_match.group(1) if prefix_match else stem
    clean_name = f"{clean_stem}{file_p.suffix}" if prefix_match else file_p.name

    tags: list[str] = []
    for candidate in (clean_name, clean_stem):
        if candidate and candidate not in tags:
            tags.append(candidate)
    return tags


def _clean_user_tags(tags: list[str] | None) -> list[str]:
    cleaned: list[str] = []
    if tags:
        for t in tags:
            clean = t.strip().lstrip("#")
            if clean and clean not in cleaned:
                cleaned.append(clean)
    return cleaned


def _prepare_tags_and_clause(
    tags: list[str] | None,
    source: str,
    source_type: SourceType,
) -> tuple[list[str], str]:
    """
    Compiles mandatory tags (user-requested + meaningful filename tags)
    and formats the prompt clause for the LLM.
    """
    tags_to_ensure = _clean_user_tags(tags)

    if source_type in (SourceType.PDF, SourceType.MARKDOWN, SourceType.IMAGE):
        for file_tag in _extract_clean_file_tags(Path(source)):
            if file_tag not in tags_to_ensure:
                tags_to_ensure.append(file_tag)

    if tags_to_ensure:
        clause = (
            f"In addition to your automatically inferred tags, you MUST also include these specific tags: "
            f"{', '.join(tags_to_ensure)}."
        )
    else:
        clause = "Select tags that best characterize the technical concepts and domain."

    return tags_to_ensure, clause


def _format_tag_item(tag: str) -> str:
    return f'"{tag}"' if any(c in tag for c in (" ", ".")) else tag


def _inject_inline_tags(md_content: str, tags_to_add: list[str]) -> str | None:
    inline_match = re.search(r"^(tags:\s*\[)(.*?)(\])", md_content, re.MULTILINE)
    if not inline_match:
        return None

    existing_tags_raw = inline_match.group(2)
    existing_tags = [t.strip().strip("'\"") for t in existing_tags_raw.split(",") if t.strip()]

    added = False
    for tag in tags_to_add:
        clean_tag = tag.strip()
        if clean_tag and clean_tag not in existing_tags:
            existing_tags.append(clean_tag)
            added = True

    if not added:
        return md_content

    formatted_tags = ", ".join(_format_tag_item(t) for t in existing_tags)
    return f"{md_content[:inline_match.start()]}tags: [{formatted_tags}]{md_content[inline_match.end():]}"


def _inject_multiline_tags(md_content: str, tags_to_add: list[str]) -> str | None:
    multiline_match = re.search(r"^(tags:\s*\n(?:\s*-\s*[^\n]+\n)+)", md_content, re.MULTILINE)
    if not multiline_match:
        return None

    block = multiline_match.group(0)
    lines_to_append = [
        f"  - {_format_tag_item(tag.strip())}\n"
        for tag in tags_to_add
        if tag.strip() and tag.strip() not in block
    ]
    if not lines_to_append:
        return md_content

    return f"{md_content[:multiline_match.end()]}{''.join(lines_to_append)}{md_content[multiline_match.end():]}"


def _inject_source_tags(md_content: str, tags_to_add: list[str]) -> str:
    """
    Ensures that specific tags (such as the uploaded filename or stem) are
    present in the YAML frontmatter tags list.
    """
    if not tags_to_add:
        return md_content

    inlined = _inject_inline_tags(md_content, tags_to_add)
    if inlined is not None:
        return inlined

    multilined = _inject_multiline_tags(md_content, tags_to_add)
    if multilined is not None:
        return multilined

    return md_content


def _inject_domain_metadata(md_content: str, domain: str) -> str:
    """Ensures domain is present in the YAML frontmatter."""
    if not domain or "domain:" in md_content:
        return md_content
    fm_match = re.search(r"^---\s*\n", md_content)
    if fm_match:
        return f"{md_content[:fm_match.end()]}domain: {domain}\n{md_content[fm_match.end():]}"
    return md_content


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
