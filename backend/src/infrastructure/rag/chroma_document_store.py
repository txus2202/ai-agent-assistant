"""
Infrastructure Adapter: ChromaDBDocumentStore

Persistent (or ephemeral) vector store implementation of IDocumentStore
using ChromaDB with the sentence-transformers embedding function (ADR-012).

Embedding model: ``all-MiniLM-L6-v2`` (local, ~80 MB, no API key required).
Distance metric:  cosine (score = 1 - cosine_distance ∈ [0, 1]).

Configuration:
    - ``ephemeral=True``      → in-memory ChromaDB (for tests, fast, no disk I/O).
    - ``persist_directory``   → path to ChromaDB storage directory.
    - Env var ``CHROMA_PERSIST_DIR`` (or legacy ``CHROMA_PATH``) → overrides default ``~/.ai-agent-assistant/chroma``.
"""
from __future__ import annotations

import os
from typing import Any

import chromadb
from chromadb.utils import embedding_functions

from src.domain.ports.document_store import IDocumentStore
from src.domain.value_objects.document_chunk import DocumentChunk, SearchFilter

_DEFAULT_CHROMA_PATH = os.path.expanduser("~/.ai-agent-assistant/chroma")
_COLLECTION_NAME = "vault_docs"
_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
_DEFAULT_TOP_K = 5


class ChromaDBDocumentStore(IDocumentStore):
    """
    ChromaDB-backed implementation of ``IDocumentStore``.

    Args:
        persist_directory: Path to the ChromaDB storage directory.
                           Falls back to ``CHROMA_PERSIST_DIR``, legacy ``CHROMA_PATH``,
                           or ``~/.ai-agent-assistant/chroma``.
        ephemeral:         If ``True``, use an in-memory (ephemeral) client.
                           Intended for tests — data is lost when the object
                           is garbage-collected.
        collection_name:   ChromaDB collection name (default: ``"vault_docs"``).
    """

    def __init__(
        self,
        persist_directory: str | None = None,
        ephemeral: bool = False,
        collection_name: str = _COLLECTION_NAME,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        if ephemeral:
            self._client: chromadb.ClientAPI = chromadb.EphemeralClient()
        elif host or os.getenv("CHROMA_HOST"):
            chroma_host = host or os.getenv("CHROMA_HOST") or "localhost"
            raw_port: int | str = port if port is not None else os.getenv("CHROMA_PORT", "8000")
            chroma_port = int(raw_port)
            self._client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
        else:
            path = (
                persist_directory
                or os.getenv("CHROMA_PERSIST_DIR")
                or os.getenv("CHROMA_PATH")
                or _DEFAULT_CHROMA_PATH
            )
            self._client = chromadb.PersistentClient(path=path)

        ef: Any = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=_EMBEDDING_MODEL
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )

    # ------------------------------------------------------------------
    # IDocumentStore implementation
    # ------------------------------------------------------------------

    def upsert(self, chunks: list[DocumentChunk]) -> None:
        if not chunks:
            return
        # ChromaDB requires non-empty metadata dicts.
        # We always include _file_path for provenance tracking and to
        # guarantee at least one field even on files with no frontmatter.
        metadatas: Any = [{"_file_path": c.file_path, **c.metadata} for c in chunks]
        self._collection.upsert(
            ids=[c.id for c in chunks],
            documents=[c.content for c in chunks],
            metadatas=metadatas,
        )

    def search(
        self,
        query: str,
        top_k: int | None = None,
        filter: SearchFilter | None = None,
    ) -> list[DocumentChunk]:
        resolved_top_k = top_k if top_k is not None else int(
            os.getenv("RAG_TOP_K", str(_DEFAULT_TOP_K))
        )
        total = self._collection.count()
        if total == 0:
            return []

        n_results = min(resolved_top_k, total)
        where = self._build_where(filter) if filter else None

        kwargs: dict = {
            "query_texts": [query],
            "n_results": n_results,
        }
        if where:
            kwargs["where"] = where

        results = self._collection.query(**kwargs)
        ids_batch = results.get("ids") or [[]]
        metadatas_batch = results.get("metadatas") or [[]]
        distances_batch = results.get("distances") or [[]]
        documents_batch = results.get("documents") or [[]]

        chunks: list[DocumentChunk] = []
        for i, doc_id in enumerate(ids_batch[0]):
            raw_meta = dict(metadatas_batch[0][i])
            distance = float(distances_batch[0][i])
            score = max(0.0, 1.0 - distance)  # cosine distance → similarity

            file_path, _, heading = doc_id.partition("#")
            chunks.append(
                DocumentChunk(
                    id=doc_id,
                    content=documents_batch[0][i],
                    file_path=file_path,
                    heading=heading,
                    metadata={k: str(v) for k, v in raw_meta.items()},
                    score=score,
                )
            )
        return chunks

    def delete(self, chunk_ids: list[str]) -> None:
        if chunk_ids:
            self._collection.delete(ids=chunk_ids)

    def delete_by_file_paths(self, file_paths: list[str]) -> None:
        if not file_paths:
            return
        for fp in file_paths:
            self._collection.delete(where={"_file_path": fp})

    def get_indexed_file_paths(self) -> set[str]:
        total = self._collection.count()
        if total == 0:
            return set()
        results = self._collection.get(include=["metadatas"])
        metadatas = results.get("metadatas") or []
        indexed: set[str] = set()
        for meta in metadatas:
            if meta and "_file_path" in meta and meta["_file_path"]:
                indexed.add(str(meta["_file_path"]))
        return indexed

    def count(self) -> int:
        return self._collection.count()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_where(filter: SearchFilter) -> dict:
        """Translate ``SearchFilter`` into a ChromaDB ``where`` clause."""
        conditions: list[dict] = []

        def _add_condition(key: str, val: Any) -> None:
            if val is None:
                return
            if isinstance(val, (list, tuple)):
                if len(val) == 1:
                    conditions.append({key: {"$eq": str(val[0])}})
                elif len(val) > 1:
                    conditions.append({key: {"$in": [str(x) for x in val]}})
            else:
                conditions.append({key: {"$eq": str(val)}})

        _add_condition("type", filter.type)
        _add_condition("layer", filter.layer)
        _add_condition("status", filter.status)
        _add_condition("phase", filter.phase)
        _add_condition("category", filter.category)
        _add_condition("domain", filter.domain)

        if not conditions:
            return {}
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}
