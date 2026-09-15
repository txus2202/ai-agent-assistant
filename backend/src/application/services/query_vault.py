"""
Application Service: QueryVault

Wraps IDocumentStore.search() with input validation and a prompt-formatting
helper used by all sub-agents to inject RAG context into their prompts.
"""
from __future__ import annotations

from src.domain.ports.document_store import IDocumentStore
from src.domain.value_objects.document_chunk import DocumentChunk, SearchFilter


class QueryVault:
    """Stateless RAG query service."""

    @staticmethod
    def run(
        query: str,
        document_store: IDocumentStore,
        filter: SearchFilter | None = None,
        top_k: int | None = None,
    ) -> list[DocumentChunk]:
        """
        Search the document store for chunks relevant to ``query``.

        Args:
            query:          Natural language query. Must be non-empty.
            document_store: The IDocumentStore to search.
            filter:         Optional metadata filter.
            top_k:          Max results. ``None`` → reads ``RAG_TOP_K`` env var.

        Raises:
            ValueError: if ``query`` is empty or whitespace-only.
        """
        if not query or not query.strip():
            raise ValueError("query cannot be empty")

        return document_store.search(query=query, top_k=top_k, filter=filter)

    @staticmethod
    def chunks_to_context(chunks: list[DocumentChunk]) -> str:
        """
        Format ``chunks`` as a Markdown context block for prompt injection.

        Returns an empty string when ``chunks`` is empty.
        Agents should prepend this block to the user message.

        Example output::

            --- Knowledge Context ---
            [docs/features/feature_run_agent_task.md — Acceptance Criteria]
            The RunAgentTask use case must...

            [DECISIONS.md — ADR 012]
            Phase 2 requires building a RAG pipeline...
            --- End Context ---
        """
        if not chunks:
            return ""

        lines: list[str] = ["--- Knowledge Context ---"]
        for chunk in chunks:
            label = f"[{chunk.file_path}"
            if chunk.heading:
                label += f" — {chunk.heading}"
            label += "]"
            lines.append(label)
            lines.append(chunk.content)
            lines.append("")  # blank line between chunks

        lines.append("--- End Context ---")
        return "\n".join(lines)
