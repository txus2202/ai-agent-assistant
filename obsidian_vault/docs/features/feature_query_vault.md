---
created: 2026-09-15
updated: 2026-09-15
type: spec
phase: 3
layer: application
status: draft
tags: [rag, query, use-case, application, context, chunks]
---

# Feature: QueryVault Use Case

**As a** sub-agent
**I want** to query the Obsidian knowledge vault semantically
**So that** I can ground my responses in ATENEA's documented architecture, decisions, and specs before answering.

## Context & Motivation

Phase 2 provides `IDocumentStore.search()`. This spec wraps it in an Application use case that:
1. Validates the query
2. Returns ranked `DocumentChunk` objects
3. Provides a `chunks_to_context()` helper that formats chunks as a prompt block — the standard interface that every sub-agent uses to inject RAG context into its prompt.

## Use Case Contract

```python
QueryVault.run(
    query: str,
    document_store: IDocumentStore,
    filter: SearchFilter | None = None,
    top_k: int | None = None,     # None → reads RAG_TOP_K env var
) -> list[DocumentChunk]
```

Raises `ValueError` if `query` is empty or whitespace-only.

## Helper: chunks_to_context

```python
QueryVault.chunks_to_context(chunks: list[DocumentChunk]) -> str
```

Formats chunks as a Markdown block for prompt injection:

```
--- Knowledge Context ---
[docs/features/feature_run_agent_task.md — Acceptance Criteria]
The RunAgentTask use case must...

[DECISIONS.md — ADR 012: RAG Pipeline Architecture]
Phase 2 requires building a RAG pipeline...
--- End Context ---
```

Returns an empty string when `chunks` is empty (agents must handle this gracefully).

## Acceptance Criteria

### Scenario 1: Returns ranked chunks for a valid query

```
Given a document store with 3 chunks about "architecture" and 2 about "testing"
When QueryVault.run(query="clean architecture layers") is called
Then chunks about architecture appear first (highest score)
```

### Scenario 2: Raises ValueError for empty query

```
Given a document store (may be empty)
When QueryVault.run(query="") is called
Then ValueError is raised with message "query cannot be empty"
```

### Scenario 3: Returns empty list when store is empty

```
Given an empty document store
When QueryVault.run(query="any valid query") is called
Then an empty list is returned (no exception)
```

### Scenario 4: SearchFilter is forwarded to the document store

```
Given a store with chunks of type "spec" and type "adr"
When QueryVault.run(query="...", filter=SearchFilter(type="spec")) is called
Then only chunks with metadata["type"] == "spec" are returned
```

### Scenario 5: chunks_to_context returns empty string for empty list

```
Given an empty list of chunks
When QueryVault.chunks_to_context([]) is called
Then "" is returned
```

### Scenario 6: chunks_to_context includes file_path and heading in output

```
Given a chunk with file_path="DECISIONS.md" and heading="ADR 012"
When QueryVault.chunks_to_context([chunk]) is called
Then the output contains "DECISIONS.md" and "ADR 012"
```

## Implementation Notes

- Lives at: `src/application/services/query_vault.py`
- `chunks_to_context` is a `@staticmethod` — no state required
- The context format uses `---` separators to be clearly delimited in prompts
- Agents should prefix their user message with the context block from `chunks_to_context`
- `top_k=None` delegates to env var `RAG_TOP_K` (already implemented in IDocumentStore adapters)
