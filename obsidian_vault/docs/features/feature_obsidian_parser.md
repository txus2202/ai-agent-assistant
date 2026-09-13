---
created: 2026-09-08
updated: 2026-09-09
type: spec
phase: 2
layer: infrastructure
status: implemented
tags: [parser, obsidian, markdown, chunking, frontmatter, infrastructure]
---

# Feature: ObsidianParser — Markdown to DocumentChunks

**As a** system operator
**I want** to parse any `.md` file in the Obsidian vault into structured `DocumentChunk` objects
**So that** the ingestion script can feed them into the vector store.

## Context & Motivation

ADR-012 establishes section-based chunking (H2/H3 boundaries) with YAML frontmatter as metadata. The `ObsidianParser` is a pure infrastructure utility — it has no domain dependencies other than `DocumentChunk`. It must handle:
- Files with no frontmatter (e.g., root-level `DECISIONS.md`, `ARCHITECTURE.md`)
- Files with no headers (single-block documents)
- Files where the first content block before any H2/H3 should be treated as an intro chunk
- Obsidian-specific syntax (`[[wikilinks]]`, `#tags`) — treat as plain text for now

## Parsing Rules

1. **Frontmatter extraction:** Strip the `---` YAML block at the top. Parse it into `metadata: dict[str, str]`. All values are stringified (e.g., `phase: 2` → `"2"`). If no frontmatter, `metadata = {}`.
2. **Intro chunk:** Text between the end of frontmatter and the first H2/H3 header (if any) is an intro chunk with `heading = ""`.
3. **Section chunks:** Each H2/H3 header starts a new chunk. The heading text becomes `chunk.heading`. Content runs until the next H2/H3 or end of file.
4. **Chunk id:** `f"{file_path}#{slugify(heading)}"`. Intro chunk uses `f"{file_path}#intro"`.
5. **Empty sections:** Sections with only whitespace after stripping are discarded.
6. **file_path:** Relative path from the vault root (e.g., `docs/features/feature_task_entity.md`).

## Acceptance Criteria

### Scenario 1: File with frontmatter and multiple H2 sections

```
Given a .md file:
  ---
  type: spec
  phase: 2
  ---
  # Title
  ## Overview
  Overview content here.
  ## Acceptance Criteria
  Criteria content here.

When  ObsidianParser.parse(file_path, vault_root) is called
Then  two chunks are returned
And   chunk[0].heading == "Overview" and chunk[0].content == "Overview content here."
And   chunk[1].heading == "Acceptance Criteria"
And   both chunks have metadata["type"] == "spec" and metadata["phase"] == "2"
```

### Scenario 2: File with no frontmatter

```
Given a .md file with no YAML block and one H2 section
When  parse() is called
Then  chunk.metadata == {}
And   the section content is correctly extracted
```

### Scenario 3: File with intro block before first H2

```
Given a .md file with text before the first H2 header
When  parse() is called
Then  an intro chunk is returned with heading == "" and the pre-header text as content
```

### Scenario 4: H3 headers create separate chunks

```
Given a .md file with one H2 and two H3 sections inside it
When  parse() is called
Then  three chunks are returned (H2 section body + two H3 sections)
```

### Scenario 5: Empty sections are discarded

```
Given a .md file where a section has only whitespace after the header
When  parse() is called
Then  that section does not appear in the output
```

### Scenario 6: chunk.id follows the slug pattern

```
Given a section with heading "Acceptance Criteria"
Then  chunk.id ends with "#acceptance-criteria"
```

### Scenario 7: Obsidian wikilinks are left as-is

```
Given a section containing "See [[ADR-011]] for details"
When  parse() is called
Then  chunk.content contains "See [[ADR-011]] for details" unchanged
```

## Implementation Notes

- **File:** `src/infrastructure/rag/obsidian_parser.py`
- **No external dependencies** beyond Python stdlib (`re`, `yaml` — use `import yaml` from PyYAML which we will add to `requirements.txt`).
- `ObsidianParser` should be a stateless class with a single static/class method `parse(file_path: Path, vault_root: Path) -> list[DocumentChunk]`.
- Use `re.split` on H2/H3 pattern: `^#{2,3}\s+(.+)$` (multiline).
- `slugify(heading)`: lowercase, replace spaces with `-`, remove non-alphanumeric except `-`.
- `PyYAML` is the only new dependency introduced. Add to `requirements.txt`.
