---
created: 2026-09-08
updated: 2026-09-08
type: spec
phase: 2
layer: infrastructure
status: draft
tags: [chromadb, rag, ingestion, cli, infrastructure, vector-store]
---

# Feature: ChromaDBDocumentStore + IngestVault CLI

**As a** system operator
**I want** to run a CLI script that ingests the entire Obsidian vault into ChromaDB
**So that** ATENEA agents can perform semantic retrieval at query time.

## Context & Motivation

`ChromaDBDocumentStore` is the Phase 2 concrete adapter for `IDocumentStore` (ADR-012). It wraps ChromaDB's Python client using its built-in sentence-transformers embedding function (`all-MiniLM-L6-v2`, local, no API key required). The `IngestVault` service orchestrates: discover `.md` files → parse with `ObsidianParser` → upsert all chunks into ChromaDB. The CLI script `scripts/ingest_vault.py` is the entry point.

## ChromaDBDocumentStore

### Configuration

| Parameter | Source | Default |
| :--- | :--- | :--- |
| `collection_name` | constructor arg | `"vault_docs"` |
| `persist_directory` | `CHROMA_PATH` env var | `~/.ai-agent-assistant/chroma` |
| Embedding function | ChromaDB default | `all-MiniLM-L6-v2` (local, via sentence-transformers) |

### Acceptance Criteria

#### Scenario 1: upsert stores chunks and count reflects them

```
Given a ChromaDBDocumentStore with a temp persist directory
When  two chunks are upserted
Then  count() == 2
```

#### Scenario 2: search returns the most semantically relevant chunk

```
Given two chunks: one about "database persistence with SQLite"
  and one about "voice recognition with Whisper"
When  search("how do we store agents?", top_k=1) is called
Then  the SQLite chunk is returned first
And   result[0].score is not None
```

#### Scenario 3: upsert is idempotent — re-ingesting does not duplicate

```
Given a chunk with id="docs/spec.md#overview" already in the store
When  the same chunk is upserted again (re-ingestion)
Then  count() remains 1
```

#### Scenario 4: search with SearchFilter(type="adr") returns only ADR chunks

```
Given chunks with type="spec" and type="adr" in the store
When  search("architecture", filter=SearchFilter(type="adr")) is called
Then  all returned chunks have metadata["type"] == "adr"
```

#### Scenario 5: delete removes the specified chunk

```
Given a chunk upserted with id="docs/file.md#intro"
When  delete(["docs/file.md#intro"]) is called
Then  count() == 0
And   the chunk does not appear in subsequent searches
```

## IngestVault Service

### Flow

```
IngestVault.run(vault_root: Path, document_store: IDocumentStore)
  → discover all .md files under vault_root (recursive, excluding .obsidian/)
  → for each file: ObsidianParser.parse(file, vault_root) → list[DocumentChunk]
  → flatten all chunks
  → document_store.upsert(all_chunks)
  → return IngestResult(files_processed, chunks_upserted, errors)
```

### Acceptance Criteria

#### Scenario 6: IngestVault processes all .md files in the vault

```
Given a temp vault directory with 3 .md files containing 2 sections each
When  IngestVault.run(vault_root, document_store) is called
Then  IngestResult.chunks_upserted == 6 (or fewer if empty sections are skipped)
And   IngestResult.files_processed == 3
And   IngestResult.errors == []
```

#### Scenario 7: IngestVault skips .obsidian/ directory

```
Given a vault with a .obsidian/ subdirectory containing .md files
When  IngestVault.run() is called
Then  files inside .obsidian/ are not ingested
```

#### Scenario 8: IngestVault is idempotent — running twice does not duplicate

```
Given a vault with 1 file and 2 sections
When  IngestVault.run() is called twice
Then  document_store.count() == 2 (not 4)
```

## CLI Script

```bash
python scripts/ingest_vault.py --vault-root obsidian_vault/ [--chroma-path ~/.ai-agent-assistant/chroma]
```

Outputs a summary:
```
✓ Processed 12 files · 47 chunks upserted · 0 errors
  Collection: vault_docs (persist: ~/.ai-agent-assistant/chroma)
```

## Implementation Notes

- **Files:**
  - `src/infrastructure/rag/chroma_document_store.py`
  - `src/application/services/ingest_vault.py`
  - `scripts/ingest_vault.py`
- **New dependencies** (add to `requirements.txt`):
  - `chromadb>=0.5`
  - `PyYAML>=6.0` (for frontmatter parsing)
- `ChromaDBDocumentStore` tests must use `tmp_path` and `chromadb.EphemeralClient()` (in-memory, no disk) to keep tests fast.
- `IngestVault` tests use `InMemoryDocumentStore` (no ChromaDB needed).
- The `SearchFilter` → ChromaDB `where` dict translation: `{"$and": [{"type": {"$eq": "adr"}}, ...]}`.
