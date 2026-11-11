"""
Tests — SubAgentRunner (Feature: feature_sub_agents.md)

Layer: Application

ADR-016: SubAgentRunner.run() is now async. Tests use @pytest.mark.anyio.

Scenarios:
  1. NL_INTERPRETER ("Interpreter") returns response without calling RAG
  2. SENIOR_ARCHITECT ("PropTwo") retrieves RAG filtered by status=implemented
  3. SubAgentRunner builds prompt including context block
  + additional edge cases
"""
from __future__ import annotations

import pytest

from src.application.agents.sub_agent_runner import SubAgentRunner
from src.domain.agents.sub_agent_profiles import get_profile
from src.domain.ports.llm_provider import ILLMProvider
from src.domain.value_objects.document_chunk import DocumentChunk
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
        llm = FakeLLM("Formalized: use hexagonal architecture")
        store = InMemoryDocumentStore()

        response = await SubAgentRunner.run(
            role="Interpreter",
            user_request="make it cleaner",
            llm_provider=llm,
            document_store=store,
            model_name="gemini-3.6-flash",
        )

        assert response.content == "Formalized: use hexagonal architecture"

    @pytest.mark.anyio
    async def test_nl_interpreter_does_not_call_rag(self):
        llm = FakeLLM()
        store = InMemoryDocumentStore()
        store.upsert([_chunk("doc#s", "some content")])

        response = await SubAgentRunner.run(
            role="Interpreter",
            user_request="help me",
            llm_provider=llm,
            document_store=store,
            model_name="gemini-3.6-flash",
        )

        assert response.context_chunks == []

    @pytest.mark.anyio
    async def test_senior_architect_retrieves_rag_with_implemented_filter(self):
        store = InMemoryDocumentStore()
        store.upsert([
            _chunk("spec#impl", "implemented feature A", metadata={"status": "implemented"}),
            _chunk("spec#draft", "draft feature B", metadata={"status": "draft"}),
        ])

        response = await SubAgentRunner.run(
            role="PropTwo",
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
        store = InMemoryDocumentStore()
        store.upsert([
            _chunk("spec#s", "architecture spec content", metadata={"type": "spec"}),
            _chunk("adr#a", "decision record content", metadata={"type": "adr"}),
        ])

        response = await SubAgentRunner.run(
            role="PropOne",
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
        llm = FakeLLM()
        profile = get_profile("Interpreter")

        await SubAgentRunner.run(
            role="Interpreter",
            user_request="test request",
            llm_provider=llm,
            document_store=InMemoryDocumentStore(),
            model_name="gemini-3.6-flash",
        )

        sent_prompt = llm.received_prompts[0]
        assert profile.system_prompt[:30] in sent_prompt

    @pytest.mark.anyio
    async def test_prompt_includes_context_when_rag_used(self):
        llm = FakeLLM()
        store = InMemoryDocumentStore()
        store.upsert([
            _chunk("spec#s", "unique_rag_content_xyz", metadata={"type": "spec"}),
        ])

        await SubAgentRunner.run(
            role="PropOne",
            user_request="propose something",
            llm_provider=llm,
            document_store=store,
            model_name="gemini-3.6-flash",
        )

        sent_prompt = llm.received_prompts[0]
        assert "unique_rag_content_xyz" in sent_prompt

    @pytest.mark.anyio
    async def test_rag_top_k_zero_skips_rag_retrieval_for_rag_agent(self):
        llm = FakeLLM()
        store = InMemoryDocumentStore()
        store.upsert([
            _chunk("spec#s", "should_not_be_retrieved_xyz", metadata={"type": "spec"}),
        ])

        response = await SubAgentRunner.run(
            role="PropOne",
            user_request="propose something without vault noise",
            llm_provider=llm,
            document_store=store,
            model_name="gemini-3.6-flash",
            rag_top_k=0,
            rag_min_score=0.3,
        )

        assert response.context_chunks == []
        sent_prompt = llm.received_prompts[0]
        assert "should_not_be_retrieved_xyz" not in sent_prompt

    @pytest.mark.anyio
    async def test_rag_top_k_limits_returned_chunks(self):
        llm = FakeLLM()
        store = InMemoryDocumentStore()
        store.upsert([
            _chunk("spec#1", "architecture spec content 1", metadata={"type": "spec"}),
            _chunk("spec#2", "architecture spec content 2", metadata={"type": "spec"}),
            _chunk("spec#3", "architecture spec content 3", metadata={"type": "spec"}),
        ])

        response = await SubAgentRunner.run(
            role="PropOne",
            user_request="architecture spec content",
            llm_provider=llm,
            document_store=store,
            model_name="gemini-3.6-flash",
            rag_top_k=1,
            rag_min_score=0.0,
        )

        assert len(response.context_chunks) == 1

    @pytest.mark.anyio
    async def test_prompt_includes_chat_history_context(self):
        llm = FakeLLM()
        history = [
            {"role": "user", "content": "¿Cómo desplegamos esto?"},
            {"role": "assistant", "agent": "PropOne", "content": "Propongo usar Cloud Run con gRPC."},
        ]

        await SubAgentRunner.run(
            role="Auditor",
            user_request="¿Qué opinas de esa propuesta?",
            llm_provider=llm,
            document_store=InMemoryDocumentStore(),
            model_name="gemini-3.6-flash",
            chat_history=history,
        )

        sent_prompt = llm.received_prompts[0]
        assert "Contexto de la Sesión Previa" in sent_prompt
        assert "Usuario: ¿Cómo desplegamos esto?" in sent_prompt
        assert "PropOne: Propongo usar Cloud Run con gRPC." in sent_prompt
        assert "## User Request\n¿Qué opinas de esa propuesta?" in sent_prompt

    @pytest.mark.anyio
    async def test_response_role_matches_requested_role(self):
        response = await SubAgentRunner.run(
            role="ImplOne",
            user_request="draw a diagram",
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            model_name="gemini-3.6-flash",
        )

        assert response.role == "ImplOne"

    @pytest.mark.anyio
    async def test_response_content_is_llm_output(self):
        response = await SubAgentRunner.run(
            role="Auditor",
            user_request="critique this",
            llm_provider=FakeLLM("This is flawed because..."),
            document_store=InMemoryDocumentStore(),
            model_name="gemini-3.6-flash",
        )

        assert response.content == "This is flawed because..."

    @pytest.mark.anyio
    async def test_supervisor_profile_injects_team_roster(self):
        from src.domain.agents.sub_agent_profiles import (
            SubAgentProfile,
            register_profile,
            unregister_profile,
        )

        sup_profile = SubAgentProfile(
            id="test_sup",
            display_name="TestSup",
            description="Supervisor for testing",
            color_hex="#123456",
            system_prompt="You are TestSup.",
            is_supervisor=True,
        )
        register_profile(sup_profile)
        try:
            llm = FakeLLM("I am the supervisor.")
            await SubAgentRunner.run(
                role="TestSup",
                user_request="Preséntate y al equipo",
                llm_provider=llm,
                document_store=InMemoryDocumentStore(),
                model_name="gemini-3.6-flash",
            )
            assert any("MIEMBROS OFICIALES DEL CONSEJO TÉCNICO" in p for p in llm.received_prompts)
        finally:
            unregister_profile("test_sup")

    @pytest.mark.anyio
    async def test_fidias_without_image_provider_injects_html5_directive(self, monkeypatch):
        from src.domain.agents.sub_agent_profiles import SubAgentProfile, register_profile, unregister_profile

        fidias_profile = SubAgentProfile(
            id="fidias",
            display_name="Fídias",
            description="UX/UI designer",
            color_hex="#ffe600",
            system_prompt="You are Fidias.",
        )
        register_profile(fidias_profile)
        try:
            monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "")
            monkeypatch.delenv("IMAGE_PROVIDER", raising=False)
            try:
                from src.presentation.api.config import get_settings
                monkeypatch.setattr(get_settings(), "image_generation_provider", "")
            except Exception:
                pass

            llm = FakeLLM("```html\n<!DOCTYPE html><html><body><h1>Mockup</h1></body></html>\n```")
            response = await SubAgentRunner.run(
                role="Fídias",
                user_request="Diseña un dashboard oscuro",
                llm_provider=llm,
                document_store=InMemoryDocumentStore(),
                model_name="gemini-3.6-flash",
            )

            assert any("DIRECTIVA DE MAQUETACIÓN VISUAL (MODO SIN GENERADOR DE IMÁGENES)" in p for p in llm.received_prompts)
            assert "<!DOCTYPE html>" in response.content
        finally:
            unregister_profile("fidias")

    @pytest.mark.anyio
    async def test_fidias_with_image_provider_generates_image_and_replaces_directive(self, monkeypatch):
        from src.domain.agents.sub_agent_profiles import SubAgentProfile, register_profile, unregister_profile
        from src.infrastructure.image_generation.service import ImageGenerationService

        fidias_profile = SubAgentProfile(
            id="fidias",
            display_name="Fídias",
            description="UX/UI designer",
            color_hex="#ffe600",
            system_prompt="You are Fidias.",
        )
        register_profile(fidias_profile)
        try:
            monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "imagen")

            async def fake_generate_and_save(prompt, provider=None):
                return "fidias_test123.png", "/api/images/fidias_test123.png"

            monkeypatch.setattr(ImageGenerationService, "generate_and_save", fake_generate_and_save)

            llm = FakeLLM(
                "Aquí tienes el concepto visual del dashboard.\n\n"
                "[GENERATE_IMAGE: Futuristic dark cybersecurity dashboard with cyan neon glowing cards, 8k]\n\n"
                "He priorizado el contraste y la claridad de métricas."
            )

            response = await SubAgentRunner.run(
                role="Fídias",
                user_request="Genera una imagen para un dashboard",
                llm_provider=llm,
                document_store=InMemoryDocumentStore(),
                model_name="gemini-3.6-flash",
            )

            assert any("DIRECTIVA DE GENERACIÓN VISUAL (MOTOR IMAGEN ACTIVO)" in p for p in llm.received_prompts)
            assert "![Futuristic dark cybersecurity dashboard" in response.content
            assert "/api/images/fidias_test123.png" in response.content
            assert "[GENERATE_IMAGE:" not in response.content
        finally:
            unregister_profile("fidias")

    @pytest.mark.anyio
    async def test_fidias_with_image_provider_failure_replaces_with_warning(self, monkeypatch):
        from src.domain.agents.sub_agent_profiles import SubAgentProfile, register_profile, unregister_profile
        from src.infrastructure.image_generation.service import ImageGenerationService

        fidias_profile = SubAgentProfile(
            id="fidias",
            display_name="Fídias",
            description="UX/UI designer",
            color_hex="#ffe600",
            system_prompt="You are Fidias.",
        )
        register_profile(fidias_profile)
        try:
            monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "imagen")

            async def fake_fail(prompt, provider=None):
                raise RuntimeError("API quota exceeded")

            monkeypatch.setattr(ImageGenerationService, "generate_and_save", fake_fail)

            llm = FakeLLM(
                "Propuesta visual:\n"
                "[GENERATE_IMAGE: Neon login page, minimalist]\n"
                "Listo para revisión."
            )

            response = await SubAgentRunner.run(
                role="Fídias",
                user_request="Crea una imagen de login",
                llm_provider=llm,
                document_store=InMemoryDocumentStore(),
                model_name="gemini-3.6-flash",
            )

            assert "No se pudo generar la imagen con imagen: API quota exceeded" in response.content
            assert "[GENERATE_IMAGE:" not in response.content
        finally:
            unregister_profile("fidias")

