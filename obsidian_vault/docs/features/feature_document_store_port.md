---
created: 2026-09-08
updated: 2026-09-08
type: spec
phase: 2
layer: domain
status: draft
tags: [port, rag, document-store, domain, interface, vector-search]
---

# Feature: Domain Port — IDocumentStore + DocumentChunk

**As a** ATENEA agent
**I want** to retrieve semantically relevant document chunks from the knowledge vault
**So that** I can answer questions grounded in project-specific context (architecture decisions, specs, notes) rather than purely on the LLM's pre-training.

## Context & Motivation

ATENEA's Obsidian vault is its long-term memory. Without RAG, agents can only use their pre-trained knowledge and the current conversation. `IDocumentStore` is the domain port that decouples retrieval logic from ChromaDB, allowing future swap to any vector database (pgvector, Qdrant, Weaviate) without touching business logic (ADR-004, ADR-012).

## Value Objects

### `DocumentChunk`

Immutable unit returned by a search operation.

| Field | Type | Description |
| :--- | :--- | :--- |
| `id` | `str` | Unique identifier: `{file_path}#{heading_slug}` |
| `content` | `str` | Raw text of the section (not the embedding) |
| `file_path` | `str` | Relative path within the vault |
| `heading` | `str` | H1/H2/H3 header of the section (empty for intro block) |
| `metadata` | `dict[str, str]` | Parsed YAML frontmatter fields (type, phase, layer, status, tags, created, updated) |
| `score` | `float \| None` | Similarity score returned by the vector store (1.0 = identical) |

### `SearchFilter`

Optional structured filter to narrow retrieval by metadata.

```python
@dataclass(frozen=True)
class SearchFilter:
    type: str | None = None      # e.g. "spec", "adr", "note"
    phase: int | None = None     # e.g. 1, 2, 3
    layer: str | None = None     # e.g. "domain", "infrastructure"
    status: str | None = None    # e.g. "implemented", "draft"
```

## Port Contract

```python
class IDocumentStore(ABC):
    def upsert(self, chunks: list[DocumentChunk]) -> None: ...
    def search(self, query: str, top_k: int = 5, filter: SearchFilter | None = None) -> list[DocumentChunk]: ...
    def delete(self, chunk_ids: list[str]) -> None: ...
    def count(self) -> int: ...
```

## Acceptance Criteria

### Scenario 1: Port is abstract

```
Given the IDocumentStore class
When  an attempt to instantiate it directly is made
Then  TypeError is raised
```

### Scenario 2: upsert + search returns semantically relevant chunks

```
Given an IDocumentStore implementation
And   chunk about "SQLite persistence for domain entities" is upserted
And   chunk about "voice integration with Whisper" is upserted
When  search("how are agents persisted?", top_k=1) is called
Then  the first result is the SQLite chunk, not the voice chunk
```

### Scenario 3: search with filter narrows results

```
Given three chunks: two with type="spec", one with type="adr"
When  search("architecture", filter=SearchFilter(type="adr")) is called
Then  only the adr chunk is returned
```

### Scenario 4: upsert is idempotent (same id = update, not duplicate)

```
Given a chunk with id="path/file.md#overview" already in the store
When  a new chunk with the same id but different content is upserted
Then  count() remains unchanged
And   search returns the updated content
```

### Scenario 5: delete removes chunks

```
Given two chunks upserted
When  delete([chunk_id]) is called
Then  count() decreases by 1
And   the deleted chunk does not appear in search results
```

## Implementation Notes

- **Port file:** `src/domain/ports/document_store.py`
- **Value objects:** `src/domain/value_objects/document_chunk.py`
- **Phase 2 adapter:** `ChromaDBDocumentStore` in `src/infrastructure/rag/`
- **Test adapter:** `InMemoryDocumentStore` in `src/infrastructure/rag/` (for unit tests, no embedding needed — use exact string match)
- `DocumentChunk` must be a frozen dataclass (immutable value object, no identity).
- `metadata` dict values must be `str` (ChromaDB restriction on metadata types).
