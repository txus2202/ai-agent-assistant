"""
Unit Tests — LearnFromSession Service
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.application.services.learn_from_session import LearnFromSession
from src.domain.ports.llm_provider import ILLMProvider
from src.infrastructure.rag.in_memory_document_store import InMemoryDocumentStore


class FakeLLM(ILLMProvider):
    def list_models(self) -> list[dict[str, str]]:
        return [{"id": "test", "name": "Test"}]

    def complete(self, prompt: str, model_name: str) -> str:
        return """---
type: solution
created: 2026-10-28
tags: [solucion, arquitectura, consenso]
session_id: test-session-123
---

# Solución de Autenticación Distribuida

## Resumen Ejecutivo
Se acordó implementar OAuth2 con tokens JWT rotativos y validación asíncrona.

## Decisiones Clave
- Atenea validó la compatibilidad con el gateway.
- Ícaro propuso cache de revocación en Redis.
"""


def test_learn_from_session_creates_solution_note_and_ingests(tmp_path: Path):
    store = InMemoryDocumentStore()
    chat_history = [
        {"role": "user", "content": "Necesitamos diseñar el sistema de autenticación."},
        {"role": "assistant", "name": "Hermes", "content": "Requisitos formalizados: OAuth2 y bajo acoplamiento."},
        {"role": "assistant", "name": "Ícaro", "content": "Propongo JWT con rotación de claves en Redis."},
        {"role": "assistant", "name": "Sphinx", "content": "Evaluación positiva con salvaguarda en expiración."},
        {"role": "assistant", "name": "Atenea", "content": "Dictamen final: Se aprueba la arquitectura de Ícaro con Redis."}
    ]

    result = LearnFromSession.run(
        session_id="test-session-123",
        chat_history=chat_history,
        llm_provider=FakeLLM(),
        document_store=store,
        vault_root=tmp_path,
        model_name="mock-model",
    )

    assert result.errors == []
    assert result.generated_file is not None
    assert result.generated_file.exists()
    assert "solucion" in result.generated_file.name

    content = result.generated_file.read_text(encoding="utf-8")
    assert "Solución de Autenticación Distribuida" in content
    assert "test-session-123" in content

    # Verificamos que se ingesta en el document store
    chunks = store.search("autenticación")
    assert len(chunks) > 0



def test_learn_from_session_handles_empty_history(tmp_path: Path):
    store = InMemoryDocumentStore()
    result = LearnFromSession.run(
        session_id="empty-session",
        chat_history=[],
        llm_provider=FakeLLM(),
        document_store=store,
        vault_root=tmp_path,
        model_name="mock-model",
    )

    assert len(result.errors) > 0
    assert "historial vacío" in result.errors[0].lower() or "empty" in result.errors[0].lower()
    assert result.generated_file is None
