"""
Tests — SubAgentRunner (Feature: feature_sub_agents.md)

Layer: Application

ADR-016: SubAgentRunner.run() is now async. Tests use @pytest.mark.anyio.
"""
from __future__ import annotations

import pytest

from src.application.agents.sub_agent_runner import SubAgentRunner
from src.domain.agents.sub_agent_profiles import SubAgentProfile
from src.domain.ports.llm_provider import ILLMProvider
from src.domain.value_objects.document_chunk import DocumentChunk
from src.infrastructure.config.yaml_agent_catalog import InMemoryAgentCatalogRepository
from src.infrastructure.rag.in_memory_document_store import InMemoryDocumentStore


class FakeLLM(ILLMProvider):
    def __init__(self, response: str = "LLM response"):
        self._response = response
        self.received_prompts: list[str] = []

    def list_models(self, probe: bool = True) -> list[dict[str, str]]:
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


class TestSubAgentRunner:
    @pytest.mark.anyio
    async def test_requires_injected_agent_catalog(self):
        llm = FakeLLM()
        store = InMemoryDocumentStore()
        with pytest.raises(ValueError, match="agent_catalog"):
            await SubAgentRunner.run(
                role="Interpreter",
                user_request="hello",
                llm_provider=llm,
                document_store=store,
                model_name="gemini-3.6-flash",
            )

    @pytest.mark.anyio
    async def test_nl_interpreter_returns_response(self, generic_catalog):
        llm = FakeLLM("Formalized: use hexagonal architecture")
        store = InMemoryDocumentStore()

        response = await SubAgentRunner.run(
            role="Interpreter",
            user_request="make it cleaner",
            llm_provider=llm,
            document_store=store,
            model_name="gemini-3.6-flash",
            agent_catalog=generic_catalog,
        )

        assert response.content == "Formalized: use hexagonal architecture"

    @pytest.mark.anyio
    async def test_nl_interpreter_does_not_call_rag(self, generic_catalog):
        llm = FakeLLM()
        store = InMemoryDocumentStore()
        store.upsert([_chunk("doc#s", "some content")])

        response = await SubAgentRunner.run(
            role="Interpreter",
            user_request="help me",
            llm_provider=llm,
            document_store=store,
            model_name="gemini-3.6-flash",
            agent_catalog=generic_catalog,
        )

        assert response.context_chunks == []

    @pytest.mark.anyio
    async def test_senior_architect_retrieves_rag_with_implemented_filter(self, generic_catalog):
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
            agent_catalog=generic_catalog,
        )

        assert len(response.context_chunks) >= 1
        for chunk in response.context_chunks:
            assert chunk.metadata.get("status") == "implemented"

    @pytest.mark.anyio
    async def test_innovator_retrieves_rag_with_spec_filter(self, generic_catalog):
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
            agent_catalog=generic_catalog,
        )

        assert len(response.context_chunks) >= 1
        for chunk in response.context_chunks:
            assert chunk.metadata.get("type") == "spec"

    @pytest.mark.anyio
    async def test_prompt_includes_system_prompt(self, generic_catalog):
        llm = FakeLLM()
        profile = generic_catalog.get_profile("Interpreter")

        await SubAgentRunner.run(
            role="Interpreter",
            user_request="test request",
            llm_provider=llm,
            document_store=InMemoryDocumentStore(),
            model_name="gemini-3.6-flash",
            agent_catalog=generic_catalog,
        )

        sent_prompt = llm.received_prompts[0]
        assert profile.system_prompt[:30] in sent_prompt

    @pytest.mark.anyio
    async def test_prompt_includes_context_when_rag_used(self, generic_catalog):
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
            agent_catalog=generic_catalog,
        )

        sent_prompt = llm.received_prompts[0]
        assert "unique_rag_content_xyz" in sent_prompt

    @pytest.mark.anyio
    async def test_rag_top_k_zero_skips_rag_retrieval_for_rag_agent(self, generic_catalog):
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
            agent_catalog=generic_catalog,
        )

        assert response.context_chunks == []
        sent_prompt = llm.received_prompts[0]
        assert "should_not_be_retrieved_xyz" not in sent_prompt

    @pytest.mark.anyio
    async def test_rag_top_k_limits_returned_chunks(self, generic_catalog):
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
            agent_catalog=generic_catalog,
        )

        assert len(response.context_chunks) == 1

    @pytest.mark.anyio
    async def test_prompt_includes_chat_history_context(self, generic_catalog):
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
            agent_catalog=generic_catalog,
        )

        sent_prompt = llm.received_prompts[0]
        assert "Contexto de la Sesión Previa" in sent_prompt
        assert "Usuario: ¿Cómo desplegamos esto?" in sent_prompt
        assert "PropOne: Propongo usar Cloud Run con gRPC." in sent_prompt
        assert "## User Request\n¿Qué opinas de esa propuesta?" in sent_prompt

    @pytest.mark.anyio
    async def test_response_role_matches_requested_role(self, generic_catalog):
        response = await SubAgentRunner.run(
            role="ImplOne",
            user_request="draw a diagram",
            llm_provider=FakeLLM(),
            document_store=InMemoryDocumentStore(),
            model_name="gemini-3.6-flash",
            agent_catalog=generic_catalog,
        )

        assert response.role == "ImplOne"

    @pytest.mark.anyio
    async def test_response_content_is_llm_output(self, generic_catalog):
        response = await SubAgentRunner.run(
            role="Auditor",
            user_request="critique this",
            llm_provider=FakeLLM("This is flawed because..."),
            document_store=InMemoryDocumentStore(),
            model_name="gemini-3.6-flash",
            agent_catalog=generic_catalog,
        )

        assert response.content == "This is flawed because..."

    @pytest.mark.anyio
    async def test_supervisor_profile_injects_team_roster(self):
        sup_profile = SubAgentProfile(
            id="test_sup",
            display_name="TestSup",
            description="Supervisor for testing",
            color_hex="#123456",
            system_prompt="You are TestSup.",
            is_supervisor=True,
        )
        worker_profile = SubAgentProfile(
            id="test_worker",
            display_name="TestWorker",
            description="Worker for testing",
            color_hex="#654321",
            system_prompt="You are TestWorker.",
        )
        catalog = InMemoryAgentCatalogRepository(profiles=[sup_profile, worker_profile])

        llm = FakeLLM("I am the supervisor.")
        await SubAgentRunner.run(
            role="TestSup",
            user_request="Preséntate y al equipo",
            llm_provider=llm,
            document_store=InMemoryDocumentStore(),
            model_name="gemini-3.6-flash",
            agent_catalog=catalog,
        )
        assert any("MIEMBROS OFICIALES DEL CONSEJO TÉCNICO" in p for p in llm.received_prompts)
        assert any("TestWorker" in p for p in llm.received_prompts)

    @pytest.mark.anyio
    async def test_visual_designer_without_image_provider_injects_html5_directive(self):
        class DisabledImageGenerator:
            def get_provider_name(self) -> str | None:
                return None

            def is_enabled(self) -> bool:
                return False

            async def generate_and_save(self, prompt: str, provider: str | None = None) -> tuple[str, str]:
                raise AssertionError("Should not generate images when disabled")

            def get_image_path(self, filename: str):
                return None

        designer_profile = SubAgentProfile(
            id="designer",
            display_name="VisualDesigner",
            description="UX/UI designer",
            color_hex="#ffe600",
            system_prompt="You are VisualDesigner.",
            tools=("code_viewer", "image_viewer"),
        )
        catalog = InMemoryAgentCatalogRepository(profiles=[designer_profile])

        llm = FakeLLM("```html\n<!DOCTYPE html><html><body><h1>Mockup</h1></body></html>\n```")
        response = await SubAgentRunner.run(
            role="VisualDesigner",
            user_request="Diseña un dashboard oscuro",
            llm_provider=llm,
            document_store=InMemoryDocumentStore(),
            model_name="gemini-3.6-flash",
            agent_catalog=catalog,
            image_generator=DisabledImageGenerator(),
        )

        assert any("DIRECTIVA DE MAQUETACIÓN VISUAL (MODO SIN GENERADOR DE IMÁGENES)" in p for p in llm.received_prompts)
        assert "<!DOCTYPE html>" in response.content

    @pytest.mark.anyio
    async def test_visual_designer_with_image_provider_generates_image_and_replaces_directive(self):
        class StubImageGenerator:
            def get_provider_name(self) -> str | None:
                return "imagen"

            def is_enabled(self) -> bool:
                return True

            async def generate_and_save(self, prompt: str, provider: str | None = None) -> tuple[str, str]:
                return "design_test123.png", "/api/images/design_test123.png"

            def get_image_path(self, filename: str):
                return None

        designer_profile = SubAgentProfile(
            id="designer",
            display_name="VisualDesigner",
            description="UX/UI designer",
            color_hex="#ffe600",
            system_prompt="You are VisualDesigner.",
            tools=("code_viewer", "image_viewer"),
        )
        catalog = InMemoryAgentCatalogRepository(profiles=[designer_profile])

        llm = FakeLLM(
            "Aquí tienes el concepto visual del dashboard.\n\n"
            "[GENERATE_IMAGE: Futuristic dark cybersecurity dashboard with cyan neon glowing cards, 8k]\n\n"
            "He priorizado el contraste y la claridad de métricas."
        )

        response = await SubAgentRunner.run(
            role="VisualDesigner",
            user_request="Genera una imagen para un dashboard",
            llm_provider=llm,
            document_store=InMemoryDocumentStore(),
            model_name="gemini-3.6-flash",
            agent_catalog=catalog,
            image_generator=StubImageGenerator(),
        )

        assert any("DIRECTIVA DE GENERACIÓN VISUAL (MOTOR IMAGEN ACTIVO)" in p for p in llm.received_prompts)
        assert "![Futuristic dark cybersecurity dashboard" in response.content
        assert "/api/images/design_test123.png" in response.content
        assert "[GENERATE_IMAGE:" not in response.content

    @pytest.mark.anyio
    async def test_visual_designer_with_image_provider_failure_replaces_with_warning(self):
        class FailingImageGenerator:
            def get_provider_name(self) -> str | None:
                return "imagen"

            def is_enabled(self) -> bool:
                return True

            async def generate_and_save(self, prompt: str, provider: str | None = None) -> tuple[str, str]:
                raise RuntimeError("API quota exceeded")

            def get_image_path(self, filename: str):
                return None

        designer_profile = SubAgentProfile(
            id="designer",
            display_name="VisualDesigner",
            description="UX/UI designer",
            color_hex="#ffe600",
            system_prompt="You are VisualDesigner.",
            tools=("code_viewer", "image_viewer"),
        )
        catalog = InMemoryAgentCatalogRepository(profiles=[designer_profile])

        llm = FakeLLM(
            "Propuesta visual:\n"
            "[GENERATE_IMAGE: Neon login page, minimalist]\n"
            "Listo para revisión."
        )

        response = await SubAgentRunner.run(
            role="VisualDesigner",
            user_request="Crea una imagen de login",
            llm_provider=llm,
            document_store=InMemoryDocumentStore(),
            model_name="gemini-3.6-flash",
            agent_catalog=catalog,
            image_generator=FailingImageGenerator(),
        )

        assert "No se pudo generar la imagen con imagen: API quota exceeded" in response.content
        assert "[GENERATE_IMAGE:" not in response.content

    @pytest.mark.anyio
    async def test_parallel_sub_agents_isolate_token_usage_on_shared_provider(self, generic_catalog):
        import asyncio
        import threading
        from src.domain.ports.llm_provider import LLMCompletion

        barrier = threading.Barrier(2, timeout=2.0)

        class ConcurrentSharedProvider(ILLMProvider):
            def list_models(self, probe: bool = True) -> list[dict[str, str]]:
                return [{"id": "shared", "name": "Shared"}]

            def complete(self, prompt: str, model_name: str) -> str:
                return self.complete_with_usage(prompt, model_name).content

            def complete_with_usage(self, prompt: str, model_name: str) -> LLMCompletion:
                is_first = "REQ_ALPHA" in prompt
                barrier.wait()
                if is_first:
                    return LLMCompletion(
                        content="answer-alpha",
                        usage={"input": 111, "output": 22, "total": 133},
                    )
                return LLMCompletion(
                    content="answer-beta",
                    usage={"input": 999, "output": 88, "total": 1087},
                )

        shared_provider = ConcurrentSharedProvider()
        store = InMemoryDocumentStore()

        res_a, res_b = await asyncio.gather(
            SubAgentRunner.run(
                role="Interpreter",
                user_request="REQ_ALPHA",
                llm_provider=shared_provider,
                document_store=store,
                model_name="gemini-2.5-flash",
                agent_catalog=generic_catalog,
            ),
            SubAgentRunner.run(
                role="Interpreter",
                user_request="REQ_BETA",
                llm_provider=shared_provider,
                document_store=store,
                model_name="gemini-2.5-flash",
                agent_catalog=generic_catalog,
            ),
        )

        assert res_a.content == "answer-alpha"
        assert res_a.tokens == {"input": 111, "output": 22, "total": 133}
        assert res_b.content == "answer-beta"
        assert res_b.tokens == {"input": 999, "output": 88, "total": 1087}

    @pytest.mark.anyio
    async def test_sub_agent_runner_computes_cached_tokens_from_rag_and_session_context(self, generic_catalog):
        store = InMemoryDocumentStore()
        store.upsert([
            _chunk(
                "arch#1",
                "Corporate microservice standard requiring mTLS and event-driven patterns across domains.",
                metadata={"type": "spec", "status": "implemented"},
            )
        ])

        res = await SubAgentRunner.run(
            role="PropOne",
            user_request=(
                "## Formalized Requirements\n"
                "Design a resilient payment gateway with strict security and mTLS."
            ),
            llm_provider=FakeLLM("Architectural proposal output"),
            document_store=store,
            model_name="gemini-3.6-flash",
            chat_history=[
                {"role": "user", "content": "Necesito una pasarela de pagos."},
                {"role": "assistant", "agent": "Interpreter", "content": "Requisitos formalizados previos."},
            ],
            agent_catalog=generic_catalog,
        )

        assert res.tokens.get("cached", 0) > 0
        assert res.tokens["cached"] <= res.tokens["input"]

    @pytest.mark.anyio
    async def test_different_agents_share_identical_static_prefix_for_provider_kv_cache(self, generic_catalog):
        store = InMemoryDocumentStore()
        store.upsert([
            _chunk(
                "shared#1",
                "Shared enterprise blueprint for zero-trust microservices.",
                metadata={"type": "spec", "status": "implemented"},
            )
        ])
        shared_history = [
            {"role": "user", "content": "Diseña una plataforma de pagos global."},
            {"role": "assistant", "agent": "Interpreter", "content": "Requisitos formalizados: baja latencia y PCI-DSS."},
        ]
        llm = FakeLLM("Agent response")

        await SubAgentRunner.run(
            role="PropOne",
            user_request="Propón arquitectura cloud-native",
            llm_provider=llm,
            document_store=store,
            model_name="gemini-3.6-flash",
            chat_history=shared_history,
            agent_catalog=generic_catalog,
        )
        await SubAgentRunner.run(
            role="PropTwo",
            user_request="Propón arquitectura corporativa estable",
            llm_provider=llm,
            document_store=store,
            model_name="gemini-3.6-flash",
            chat_history=shared_history,
            agent_catalog=generic_catalog,
        )

        prompt_one, prompt_two = llm.received_prompts[0], llm.received_prompts[1]
        p1_profile = generic_catalog.get_profile("PropOne")
        p2_profile = generic_catalog.get_profile("PropTwo")

        # Both prompts must start with the shared session history and RAG context BEFORE each agent's system_prompt
        assert prompt_one.startswith("## Contexto de la Sesión Previa")
        assert prompt_two.startswith("## Contexto de la Sesión Previa")
        assert prompt_one.index("## Contexto de la Sesión Previa") < prompt_one.index(p1_profile.system_prompt)
        assert prompt_one.index("Shared enterprise blueprint") < prompt_one.index(p1_profile.system_prompt)
        assert prompt_two.index("Shared enterprise blueprint") < prompt_two.index(p2_profile.system_prompt)

        # The static prefix up to each agent's system_prompt must be 100% identical byte-for-byte
        prefix_one = prompt_one[: prompt_one.index(p1_profile.system_prompt)]
        prefix_two = prompt_two[: prompt_two.index(p2_profile.system_prompt)]
        assert prefix_one == prefix_two
        assert len(prefix_one) > 100


