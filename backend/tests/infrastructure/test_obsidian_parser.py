"""
RED tests for ObsidianParser.

Spec: obsidian_vault/docs/features/feature_obsidian_parser.md
Phase: 2 | Layer: Infrastructure

These tests are pure Python — no external API or vector store needed.
They use tmp_path to create real .md files on disk.
"""
from pathlib import Path

import pytest

from src.infrastructure.rag.obsidian_parser import ObsidianParser


# ---------------------------------------------------------------------------
# Scenario 1: File with frontmatter and multiple H2 sections
# ---------------------------------------------------------------------------

def test_parse_file_with_frontmatter_and_h2_sections(tmp_path: Path) -> None:
    md = tmp_path / "feature.md"
    md.write_text(
        "---\n"
        "type: spec\n"
        "phase: 2\n"
        "status: draft\n"
        "---\n"
        "\n"
        "# Title\n"
        "\n"
        "## Overview\n"
        "Overview content here.\n"
        "\n"
        "## Acceptance Criteria\n"
        "Criteria content here.\n",
        encoding="utf-8",
    )

    chunks = ObsidianParser.parse(md, vault_root=tmp_path)

    assert len(chunks) == 2
    overview = next(c for c in chunks if c.heading == "Overview")
    criteria = next(c for c in chunks if c.heading == "Acceptance Criteria")

    assert "Overview content here." in overview.content
    assert "Criteria content here." in criteria.content
    assert overview.metadata["type"] == "spec"
    assert overview.metadata["phase"] == "2"
    assert criteria.metadata["status"] == "draft"


# ---------------------------------------------------------------------------
# Scenario 2: File with no frontmatter
# ---------------------------------------------------------------------------

def test_parse_file_with_no_frontmatter(tmp_path: Path) -> None:
    md = tmp_path / "plain.md"
    md.write_text(
        "## Single Section\n"
        "Content without frontmatter.\n",
        encoding="utf-8",
    )

    chunks = ObsidianParser.parse(md, vault_root=tmp_path)

    assert len(chunks) == 1
    assert chunks[0].metadata == {}
    assert "Content without frontmatter." in chunks[0].content


# ---------------------------------------------------------------------------
# Scenario 3: File with intro block before first H2
# ---------------------------------------------------------------------------

def test_parse_generates_intro_chunk_for_pre_header_content(tmp_path: Path) -> None:
    md = tmp_path / "doc.md"
    md.write_text(
        "---\ntype: note\n---\n"
        "\n"
        "This is the intro text before any section.\n"
        "\n"
        "## Section One\n"
        "Section content.\n",
        encoding="utf-8",
    )

    chunks = ObsidianParser.parse(md, vault_root=tmp_path)

    headings = [c.heading for c in chunks]
    assert "" in headings  # intro chunk has empty heading
    intro = next(c for c in chunks if c.heading == "")
    assert "intro text" in intro.content


# ---------------------------------------------------------------------------
# Scenario 4: H3 headers create separate chunks
# ---------------------------------------------------------------------------

def test_parse_h3_headers_create_separate_chunks(tmp_path: Path) -> None:
    md = tmp_path / "deep.md"
    md.write_text(
        "## Top Section\n"
        "Intro of top section.\n"
        "\n"
        "### Sub Section A\n"
        "Content A.\n"
        "\n"
        "### Sub Section B\n"
        "Content B.\n",
        encoding="utf-8",
    )

    chunks = ObsidianParser.parse(md, vault_root=tmp_path)

    headings = {c.heading for c in chunks}
    assert "Top Section" in headings
    assert "Sub Section A" in headings
    assert "Sub Section B" in headings


# ---------------------------------------------------------------------------
# Scenario 5: Empty sections are discarded
# ---------------------------------------------------------------------------

def test_parse_discards_empty_sections(tmp_path: Path) -> None:
    md = tmp_path / "sparse.md"
    md.write_text(
        "## Real Section\n"
        "Actual content here.\n"
        "\n"
        "## Empty Section\n"
        "   \n"
        "\n"
        "## Another Real Section\n"
        "More content.\n",
        encoding="utf-8",
    )

    chunks = ObsidianParser.parse(md, vault_root=tmp_path)

    headings = [c.heading for c in chunks]
    assert "Real Section" in headings
    assert "Another Real Section" in headings
    assert "Empty Section" not in headings


# ---------------------------------------------------------------------------
# Scenario 6: chunk.id follows the slug pattern
# ---------------------------------------------------------------------------

def test_chunk_id_follows_slug_pattern(tmp_path: Path) -> None:
    md = tmp_path / "spec.md"
    md.write_text(
        "## Acceptance Criteria\n"
        "Some criteria.\n",
        encoding="utf-8",
    )

    chunks = ObsidianParser.parse(md, vault_root=tmp_path)

    assert len(chunks) == 1
    assert chunks[0].id.endswith("#acceptance-criteria")


# ---------------------------------------------------------------------------
# Scenario 7: Obsidian wikilinks are left as-is
# ---------------------------------------------------------------------------

def test_parse_preserves_wikilinks(tmp_path: Path) -> None:
    md = tmp_path / "linked.md"
    md.write_text(
        "## References\n"
        "See [[ADR-011]] for details and [[feature_task_entity]] for context.\n",
        encoding="utf-8",
    )

    chunks = ObsidianParser.parse(md, vault_root=tmp_path)

    assert len(chunks) == 1
    assert "[[ADR-011]]" in chunks[0].content
    assert "[[feature_task_entity]]" in chunks[0].content


# ---------------------------------------------------------------------------
# Extra: file_path is relative to vault root
# ---------------------------------------------------------------------------

def test_chunk_file_path_is_relative_to_vault_root(tmp_path: Path) -> None:
    subdir = tmp_path / "docs" / "features"
    subdir.mkdir(parents=True)
    md = subdir / "feature_x.md"
    md.write_text(
        "## Section\nContent.\n",
        encoding="utf-8",
    )

    chunks = ObsidianParser.parse(md, vault_root=tmp_path)

    assert chunks[0].file_path == "docs/features/feature_x.md"


# ---------------------------------------------------------------------------
# Extra: metadata values are all strings
# ---------------------------------------------------------------------------

def test_metadata_values_are_strings(tmp_path: Path) -> None:
    """ChromaDB requires all metadata values to be str/int/float/bool."""
    md = tmp_path / "typed.md"
    md.write_text(
        "---\n"
        "phase: 2\n"       # int in YAML — must be str in chunk
        "tags: [rag, ai]\n"  # list in YAML — must be str in chunk
        "---\n"
        "## Section\nContent.\n",
        encoding="utf-8",
    )

    chunks = ObsidianParser.parse(md, vault_root=tmp_path)

    for value in chunks[0].metadata.values():
        assert isinstance(value, str), f"Metadata value {value!r} is not a str"
