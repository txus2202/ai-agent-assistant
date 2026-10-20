"""
Tests — SubAgentRunner (Feature: feature_sub_agents.md)

Layer: Application

ADR-016: SubAgentRunner.run() is now async. Tests use @pytest.mark.anyio.

Scenarios:
  1. NL_INTERPRETER returns response without calling RAG
  2. SENIOR_ARCHITECT retrieves RAG filtered by status=implemented
  3. SubAgentRunner builds prompt including context block
  + additional edge cases
"""
from __future__ import annotations

import pytest

from src.domain.ports.llm_provider import ILLMProvider
from src.domain.value_objects.document_chunk import DocumentChunk, SearchFilter
from src.infrastructure.rag.in_memory_document_store import InMemoryDocumentStore


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------

class FakeLLM(ILLMProvider):
    def __init__(self, response: str = "LLM response"):
        self._response = response
        self.received_prompts: list[str] = []

    def list_models(self) -> list[dict[str, str]]:
        return [{"id": "test", "name": "Test"}]

    def complete(self, prompt: str, model_name: str) -> str:
        self.received_prompts.append(prompt)
        return self._response


def _chunk(chunk_id: str, content: str, metadata: dict | None = None) -> DocumentChunk:
    return DocumentChunk(
        id=chunk_id,
        content=content,
        file_path="doc.md",
        heading="Section",
        metadata=metadata or {},
        score=None,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSubAgentRunner:
    @pytest.mark.anyio
    async def test_nl_interpreter_returns_response(self):
        from src.domain.agents.sub_agent_profiles import AgentRole
        from src.application.agents.sub_agent_runner import SubAgentRunner

        llm = FakeLLM("Formalized: use hexagonal architecture")
        store = InMemoryDocumentStore()

        response = await SubAgentRunner.run(
            role=AgentRole.NL_INTERPRETER,
            user_request="make it cleaner",
            llm_provider=llm,
            document_store=store,
            model_name="gemini-3.6-flash",
        )

        assert response.content == "Formalized: use hexagonal architecture"

    @pytest.mark.anyio
    async def test_nl_interpreter_does_not_call_rag(self):
        from src.domain.agents.sub_agent_profiles import AgentRole
        from src.application.agents.sub_agent_runner import SubAgentRunner

        llm = FakeLLM()
        store = InMemoryDocumentStore()
        store.upsert([_chunk("doc#s", "some content")])

        response = await SubAgentRunner.run(
            role=AgentRole.NL_INTERPRETER,
            user_request="help me",
            llm_provider=llm,
            document_store=store,
            model_name="gemini-3.6-flash",
        )

        assert response.context_chunks == []

    @pytest.mark.anyio
    async def test_senior_architect_retrieves_rag_with_implemented_filter(self):
        from src.domain.agents.sub_agent_profiles import AgentRole
        from src.application.agents.sub_agent_runner import SubAgentRunner

        store = InMemoryDocumentStore()
        store.upsert([
            _chunk("spec#impl", "implemented feature A", metadata={"status": "implemented"}),
            _chunk("spec#draft", "draft feature B", metadata={"status": "draft"}),
        ])

        response = await SubAgentRunner.run(
            role=AgentRole.SENIOR_ARCHITECT,
            user_request="review the codebase",
            llm_provider=FakeLLM(),
            document_store=store,
            model_name="gemini-3.6-flash",
        )

        assert len(response.context_chunks) >= 1
        for chunk in response.context_chunks:
            assert chunk.metadata.get("status") == "implemented"

    @pytest.mark.anyio
    async def test_innovator_retrieves_rag_with_spec_filter(self):
        from src.domain.agents.sub_agent_profiles import AgentRole
        from src.application.agents.sub_agent_runner import SubAgentRunner

        store = InMemoryDocumentStore()
        store.upsert([
            _chunk("spec#s", "architecture spec content", metadata={"type": "spec"}),
            _chunk("adr#a", "decision record content", metadata={"type": "adr"}),
        ])

        response = await SubAgentRunner.run(
            role=AgentRole.INNOVATOR,
            user_request="propose something new",
            llm_provider=FakeLLM(),
            document_store=store,
            model_name="gemini-3.6-flash",
        )

        assert len(response.context_chunks) >= 1
        for chunk in response.context_chunks:
            assert chunk.metadata.get("type") == "spec"

    @pytest.mark.anyio
    async def test_prompt_includes_system_prompt(self):
        from src.domain.agents.sub_agent_profiles import AgentRole
        from src.domain.agents.sub_agent_profiles import get_profile
        from src.application.agents.sub_agent_runner import SubAgentRunner

        llm = FakeLLM()
        profile = get_profile(AgentRole.NL_INTERPRETER)

        await SubAgentRunner.run(
            role=AgentRole.NL_INTERPRETER,
            user_request="test request",
            llm_provider=llm,
            document_store=InMemoryDocumentStore(),
            model_name="gemini-3.6-flash",
        )

        sent_prompt = llm.received_prompts[0]
        assert profile.system_prompt[:30] in sent_prompt

    @pytest.mark.anyio
    async def test_prompt_includes_context_when_rag_used(self):
        from src.domain.agents.sub_agent_profiles import AgentRole
        from src.application.agents.sub_agent_runner import SubAgentRunner

        llm = FakeLLM()
        store = InMemoryDocumentStore()
        store.upsert([
            _chunk("spec#s", "unique_rag_content_xyz", metadata={"type": "spec"}),
        ])

        await SubAgentRunner.run(
            role=AgentRole.INNOVATOR,
            user_request="propose something",
            llm_provider=llm,
            document_store=store,
            model_name="gemini-3.6-flash",
        )

        sent_prompt = llm.received_prompts[0]
        assert "unique_rag_content_xyz" in sent_prompt

    @pytest.mark.anyio
    async def test_prompt_includes_chat_history_context(self):
        from src.domain.agents.sub_agent_profiles import AgentRole
        from src.application.agents.sub_agent_runner import SubAgentRunner

        llm = FakeLLM()
        history = [
            {"role": "user", "content": "¿Cómo desplegamos esto?"},
            {"role": "assistant", "agent": "Ícaro", "content": "Propongo usar Cloud Run con gRPC."},
        ]

        await SubAgentRunner.run(
            role=AgentRole.THE_JUDGE,
            user_request="¿Qué opinas de esa propuesta?",
            llm_provider=llm,
            document_store=InMemoryDocumentStore(),
            model_name="gemini-3.6-flash",
            chat_history=history,
        )

        sent_prompt = llm.received_prompts[0]
        assert "Contexto de la Sesión Previa" in sent_prompt
        assert "Usuario: ¿Cómo desplegamos esto?" in sent_prompt
        assert "Ícaro: Propongo usar Cloud Run con gRPC." in sent_prompt
        assert "## User Request\n¿Qué opinas de esa propuesta?" in sent_prompt

    @pytest.mark.anyio
    async def test_response_role_matches_requested_role(self):
        from src.domain.agents.sub_agent_profiles import AgentRole
        from src.application.agents.sub_agent_runner import SubAgentRunner

        response = await SubAgentRunner.run(
            role=AgentRole.DIAGRAMMER,
            user_request="draw a diagram",
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            model_name="gemini-3.6-flash",
        )

        assert response.role == AgentRole.DIAGRAMMER

    @pytest.mark.anyio
    async def test_response_content_is_llm_output(self):
        from src.domain.agents.sub_agent_profiles import AgentRole
        from src.application.agents.sub_agent_runner import SubAgentRunner

        response = await SubAgentRunner.run(
            role=AgentRole.THE_JUDGE,
            user_request="critique this",
            llm_provider=FakeLLM("This is flawed because..."),
            document_store=InMemoryDocumentStore(),
            model_name="gemini-3.6-flash",
        )

        assert response.content == "This is flawed because..."
