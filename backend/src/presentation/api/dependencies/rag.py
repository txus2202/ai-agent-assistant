"""
Presentation Dependency: RAG Document Store

Manages a single shared IDocumentStore (ChromaDBDocumentStore) cached on
`app.state.document_store` so embedding models are loaded once per application
instance and offloaded from the asyncio event loop during creation.
"""
from __future__ import annotations

import asyncio
from typing import Any

from starlette.requests import HTTPConnection

from src.domain.ports.document_parser import IDocumentParser
from src.domain.ports.document_store import IDocumentStore
from src.infrastructure.rag.chroma_document_store import ChromaDBDocumentStore
from src.infrastructure.rag.obsidian_parser import ObsidianParser
from src.presentation.api.config import Settings, get_settings

_fallback_lock = asyncio.Lock()


def build_document_parser() -> IDocumentParser:
    """Build the default Obsidian IDocumentParser adapter."""
    return ObsidianParser()


def get_document_parser(connection: HTTPConnection) -> IDocumentParser:
    """Resolve the singleton IDocumentParser stored on `app.state.document_parser`."""
    app_state = getattr(getattr(connection, "app", None), "state", None)
    existing = getattr(app_state, "document_parser", None) if app_state is not None else None
    if existing is not None:
        return existing
    parser = build_document_parser()
    if app_state is not None:
        app_state.document_parser = parser
    return parser


def create_document_store(settings: Settings) -> IDocumentStore:
    """Instantiate ChromaDBDocumentStore using application settings."""
    store_kwargs: dict[str, Any] = {}
    if settings.chroma_host:
        store_kwargs["host"] = settings.chroma_host
        store_kwargs["port"] = settings.chroma_port
    return ChromaDBDocumentStore(
        persist_directory=str(settings.chroma_persist_dir),
        **store_kwargs,
    )


async def get_document_store(connection: HTTPConnection) -> IDocumentStore:
    """Return the singleton IDocumentStore stored on `app.state.document_store`."""
    app = getattr(connection, "app", None)
    app_state = getattr(app, "state", None)
    settings = getattr(app_state, "settings", None) or get_settings()

    if app_state is not None:
        existing = getattr(app_state, "document_store", None)
        if existing is not None:
            return existing

        lock = getattr(app_state, "_document_store_lock", None)
        if lock is None:
            lock = asyncio.Lock()
            setattr(app_state, "_document_store_lock", lock)

        async with lock:
            existing = getattr(app_state, "document_store", None)
            if existing is not None:
                return existing
            store = await asyncio.to_thread(create_document_store, settings)
            setattr(app_state, "document_store", store)
            return store

    async with _fallback_lock:
        return await asyncio.to_thread(create_document_store, settings)

