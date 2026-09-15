"""
Infrastructure Utility: ObsidianParser

Parses Obsidian-flavoured Markdown files into ``DocumentChunk`` objects
for ingestion into the vector store (ADR-012).

Parsing rules:
  1. YAML frontmatter (---block---) → metadata dict (all values as str).
  2. Text before the first H2/H3 (excluding H1 title) → intro chunk (heading="").
  3. Each H2/H3 header starts a new chunk; content runs to next header or EOF.
  4. Empty sections (whitespace-only content) are discarded.
  5. ``chunk.id`` = ``"{relative_path}#{slugify(heading)}"``
     Intro chunk id = ``"{relative_path}#intro"``
  6. Obsidian wikilinks ``[[...]]`` and tags ``#tag`` are left as-is.

Dependencies: PyYAML (stdlib re, pathlib).
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

from src.domain.value_objects.document_chunk import DocumentChunk

# Matches the YAML frontmatter block at the start of the file
_FRONTMATTER_RE = re.compile(r"^[ \t]*---[ \t]*\n(.*?)\n---[ \t]*\n", re.DOTALL)

# Matches H2 or H3 headers (## or ###) at line start
_HEADER_RE = re.compile(r"^(#{2,3})[ \t]+(\S.*)$", re.MULTILINE)

# Matches H1 headers — stripped from the intro block
_H1_RE = re.compile(r"^#[ \t]+.+\n?", re.MULTILINE)


class ObsidianParser:
    """Stateless parser — all methods are class-level."""

    @classmethod
    def parse(cls, file_path: Path, vault_root: Path) -> list[DocumentChunk]:
        """
        Parse a single Markdown file into a list of ``DocumentChunk`` objects.

        Args:
            file_path:  Absolute path to the ``.md`` file.
            vault_root: Absolute path to the vault root (used to compute
                        the relative ``file_path`` stored in each chunk).

        Returns:
            List of non-empty chunks. May be empty if the file has no content.
        """
        raw = file_path.read_text(encoding="utf-8")
        relative_path = file_path.relative_to(vault_root).as_posix()

        # ── 1. Extract frontmatter ────────────────────────────────────────
        metadata: dict[str, str] = {}
        fm_match = _FRONTMATTER_RE.match(raw)
        if fm_match:
            parsed = yaml.safe_load(fm_match.group(1)) or {}
            metadata = cls._stringify_metadata(parsed)
            raw = raw[fm_match.end():]

        # ── 2. Find all H2/H3 header positions ───────────────────────────
        headers = list(_HEADER_RE.finditer(raw))
        chunks: list[DocumentChunk] = []

        if not headers:
            # No headers → whole file is one intro chunk
            text = _H1_RE.sub("", raw).strip()
            if text:
                chunks.append(cls._make_chunk(relative_path, "", text, metadata))
            return chunks

        # ── 3. Intro chunk (before first H2/H3) ──────────────────────────
        intro_text = _H1_RE.sub("", raw[: headers[0].start()]).strip()
        if intro_text:
            chunks.append(cls._make_chunk(relative_path, "", intro_text, metadata))

        # ── 4. Section chunks ─────────────────────────────────────────────
        for idx, header in enumerate(headers):
            heading = header.group(2).strip()
            start = header.end()
            end = headers[idx + 1].start() if idx + 1 < len(headers) else len(raw)
            section_text = raw[start:end].strip()

            if not section_text:
                continue  # discard empty sections (Scenario 5)

            chunks.append(cls._make_chunk(relative_path, heading, section_text, metadata))

        return chunks

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_chunk(
        relative_path: str,
        heading: str,
        content: str,
        metadata: dict[str, str],
    ) -> DocumentChunk:
        slug = ObsidianParser._slugify(heading) if heading else "intro"
        chunk_id = f"{relative_path}#{slug}"
        return DocumentChunk(
            id=chunk_id,
            content=content,
            file_path=relative_path,
            heading=heading,
            metadata=metadata,
            score=None,
        )

    @staticmethod
    def _slugify(text: str) -> str:
        """Convert heading text to a URL-safe slug."""
        text = text.lower()
        text = re.sub(r"[^a-z0-9\s-]", "", text)
        text = re.sub(r"\s+", "-", text.strip())
        text = re.sub(r"-+", "-", text)
        return text

    @staticmethod
    def _stringify_metadata(raw: dict) -> dict[str, str]:
        """
        Flatten all YAML values to strings.

        ChromaDB requires metadata values to be str/int/float/bool.
        We normalise everything to str to keep the contract simple.
        Lists (e.g. YAML ``tags``) are joined as comma-separated strings.
        """
        result: dict[str, str] = {}
        for key, value in raw.items():
            if isinstance(value, list):
                result[str(key)] = ", ".join(str(v) for v in value)
            else:
                result[str(key)] = str(value)
        return result
