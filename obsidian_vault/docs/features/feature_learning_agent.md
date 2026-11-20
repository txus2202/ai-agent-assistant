---
created: 2026-09-15
updated: 2026-09-15
type: spec
phase: 3
layer: application
status: implemented
tags: [learning, apprentice, pdf, url, markdown, ingestion, application, atenea]
category: meta-project
---

# Feature: Learning Agent (Apprentice)

**As a** user
**I want** to feed external sources (PDFs, web URLs) to ATENEA
**So that** the system learns new knowledge, stores it as structured Markdown in the vault, and makes it immediately available for RAG retrieval.

## Context & Motivation

Registered in ADR-012 (§4) and ROADMAP Phase 3. The Learning Agent closes the full knowledge loop:

```
External source → structured .md → obsidian_vault/learned/ → ChromaDB
```

Generated `.md` files must follow the vault convention (YAML frontmatter + H2/H3 structure) to be compatible with `ObsidianParser` and the existing ingestion pipeline.

**Phase 3 scope:** PDF files and web URLs only. Image support deferred to Phase 4 (ADR-014).

## Pipeline

```
LearnFromSource.run(source, source_type, llm_provider, document_store, vault_root)
    │
    ├─ Extractor (Infrastructure)
    │   ├─ PDFExtractor  → raw text via PyMuPDF
    │   └─ URLExtractor  → clean text via httpx + beautifulsoup4
    │
    ├─ LLM: generate structured .md
    │   (system prompt enforces YAML frontmatter + H2/H3 structure)
    │
    ├─ Save to vault_root/learned/{slug}.md
    │
    └─ IngestVault.run(vault_root, document_store)
        → updates ChromaDB with new chunks
        → returns IngestResult
```

## Service Contract

```python
@dataclass
class LearnResult:
    source: str
    generated_file: Path       # absolute path of the saved .md
    ingest_result: IngestResult
    errors: list[str]

class SourceType(Enum):
    PDF = "pdf"
    URL = "url"

LearnFromSource.run(
    source: str,                    # path to PDF or URL string
    source_type: SourceType,
    llm_provider: ILLMProvider,
    document_store: IDocumentStore,
    vault_root: Path,
    model_name: str = "gemini-1.5-flash",
) -> LearnResult
```

## LLM Prompt for Structured .md Generation

The LLM receives:
- `SYSTEM`: strict instructions to generate a `.md` with YAML frontmatter and H2/H3 structure
- `USER`: the raw extracted text

The system prompt enforces:
```
Generate a Markdown document with:
1. YAML frontmatter: type, created, tags, source_url/source_file
2. A single H1 title summarising the document
3. One H2 section per major concept (3–8 sections)
4. Each H2 may contain H3 subsections for detail
5. No raw lists at the top level — all content inside sections
6. Concise, factual language; no filler text
```

## Extractor Strategy (Infrastructure)

```
src/infrastructure/learning/
    __init__.py
    pdf_extractor.py      → PDFExtractor.extract(path: Path) -> str
    url_extractor.py      → URLExtractor.extract(url: str) -> str
```

Both raise `ExtractionError` (domain exception) on failure, wrapping their internal exceptions.

## File Naming Convention

Saved files use a slug derived from the LLM-generated H1 title:
```
obsidian_vault/learned/2026-09-15_clean-architecture-in-python.md
```
Format: `{date}_{slug}.md` — sortable and traceable.

## Acceptance Criteria

### Scenario 1: PDF source generates a valid .md file

```
Given a valid PDF file at /tmp/test.pdf
When LearnFromSource.run(source="/tmp/test.pdf", source_type=SourceType.PDF, ...)
Then a .md file is created in vault_root/learned/
And the file contains valid YAML frontmatter
And the file contains at least one H2 section
```

### Scenario 2: URL source generates a valid .md file

```
Given a reachable URL "https://example.com/article"
When LearnFromSource.run(source="https://...", source_type=SourceType.URL, ...)
Then a .md file is created in vault_root/learned/
And the frontmatter contains source_url: "https://example.com/article"
```

### Scenario 3: Generated .md is immediately queryable via RAG

```
Given LearnFromSource.run() has completed successfully
When QueryVault.run(query="topic from the learned document") is called
Then at least one chunk from the learned file appears in results
```

### Scenario 4: PDF extractor raises ExtractionError for corrupt files

```
Given a corrupt / non-PDF file at /tmp/bad.pdf
When PDFExtractor.extract(Path("/tmp/bad.pdf")) is called
Then ExtractionError is raised (not PyMuPDF's internal exception)
```

### Scenario 5: URL extractor raises ExtractionError for unreachable URLs

```
Given an unreachable URL "https://this-does-not-exist-atenea.invalid"
When URLExtractor.extract("https://...") is called
Then ExtractionError is raised (not httpx's internal exception)
```

### Scenario 6: LearnResult reports errors without raising

```
Given a source that the extractor fails to parse
When LearnFromSource.run() is called
Then a LearnResult is returned with errors populated
And generated_file is None
And no exception is raised to the caller
```

### Scenario 7: Re-learning the same source is idempotent

```
Given LearnFromSource.run() called twice with the same URL
When the second call completes
Then ChromaDB count does not double (upsert replaces by chunk ID)
And only one .md file exists in learned/ (overwritten)
```

## Implementation Notes

- `LearnFromSource` lives at: `src/application/services/learn_from_source.py`
- Extractors live at: `src/infrastructure/learning/`
- `ExtractionError` added to `src/domain/exceptions.py`
- Tests use `tmp_path` fixture + small real PDF fixtures + mocked httpx responses
- The LLM call is mocked in unit tests (deterministic generated .md)
- `PyMuPDF` (fitz), `httpx`, `beautifulsoup4` added to `requirements.txt`
- CLI entry point: `scripts/learn.py` (Phase 3 closing deliverable)
