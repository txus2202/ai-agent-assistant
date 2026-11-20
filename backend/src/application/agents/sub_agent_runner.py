"""
Application Agent: SubAgentRunner

Executes a single specialized sub-agent:
  1. Load the SubAgentProfile for the requested role
  2. If uses_rag: query the vault and build context block
  3. Build prompt: system_prompt + context + user_request
  4. Call llm_provider.complete()
  5. Return SubAgentResponse

ADR-016: Converted to async def to support WebSocket streaming in Phase 4.
Business logic is unchanged — the only difference is `await` on the LLM call.
The ILLMProvider.complete() interface remains synchronous; it is called via
asyncio.to_thread() here so the event loop is not blocked.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from src.application.services.query_vault import QueryVault
from src.domain.agents.sub_agent_profiles import SubAgentProfile, format_team_roster
from src.domain.ports.agent_catalog_repository import IAgentCatalogRepository
from src.domain.ports.document_store import IDocumentStore
from src.domain.ports.image_generator import IImageGenerator
from src.domain.ports.llm_provider import ILLMProvider, invoke_llm_with_usage
from src.domain.value_objects.document_chunk import DocumentChunk

logger = logging.getLogger(__name__)


@dataclass
class SubAgentResponse:
    """Result returned by SubAgentRunner.run()."""

    role: str
    content: str
    context_chunks: list[DocumentChunk] = field(default_factory=list)
    tokens: dict[str, int] = field(default_factory=dict)
    latency: float = 0.0
    model_name: str = ""


def format_chat_history(chat_history: list[dict[str, Any]] | None, max_messages: int = 10) -> str:
    """Format recent session chat messages into an bounded context block."""
    if not chat_history:
        return ""
    
    recent = chat_history[-max_messages:]
    lines = []
    for msg in recent:
        role = msg.get("role", "")
        agent = msg.get("agent", "")
        content = str(msg.get("content", "")).strip()
        if not content:
            continue
        # Truncate very long messages to avoid blowing context window on N100
        if len(content) > 1200:
            content = content[:1200] + "... [truncado]"
            
        if role == "user":
            lines.append(f"Usuario: {content}")
        else:
            sender = agent if agent else "Asistente"
            lines.append(f"{sender}: {content}")

    if not lines:
        return ""
        
    return "## Contexto de la Sesión Previa (Historial del Chat)\n" + "\n\n".join(lines)


class SubAgentRunner:
    """Stateless async runner for a single sub-agent invocation."""

    @classmethod
    def _retrieve_rag_context(
        cls,
        profile: SubAgentProfile,
        user_request: str,
        document_store: IDocumentStore,
        rag_top_k: int | None = None,
        rag_min_score: float | None = None,
    ) -> tuple[list[DocumentChunk], str]:
        if not profile.uses_rag or rag_top_k == 0:
            return [], ""
        chunks = QueryVault.run(
            query=user_request,
            document_store=document_store,
            filter=profile.rag_filter,
            top_k=rag_top_k,
            min_score=rag_min_score,
        )
        return chunks, QueryVault.chunks_to_context(chunks)

    @classmethod
    def _build_visual_directive(cls, image_provider: str | None) -> str:
        if image_provider:
            return (
                f"## DIRECTIVA DE GENERACIÓN VISUAL (MOTOR {image_provider.upper()} ACTIVO)\n"
                f"Tienes activo el motor de generación de imágenes '{image_provider}'.\n"
                "Cuando el usuario solicite diseñar o generar una imagen, recurso gráfico, logotipo, ilustración o concepto visual de interfaz:\n"
                "1. Proporciona una breve explicación técnica y estética de tu propuesta en español.\n"
                "2. Incluye obligatoriamente en una línea independiente la directiva para generar la imagen real:\n"
                "[GENERATE_IMAGE: <detailed English visual prompt describing the interface or graphic with style, composition, colors, and 8k quality>]\n"
                "El sistema interceptará esta directiva, generará el archivo de imagen real mediante dicho motor y lo presentará al usuario."
            )
        return (
            "## DIRECTIVA DE MAQUETACIÓN VISUAL (MODO SIN GENERADOR DE IMÁGENES)\n"
            "No hay ningún motor de generación de imágenes rasterizadas (PNG/JPG) activo en el entorno.\n"
            "Por lo tanto, ante cualquier solicitud de diseño de interfaz, mockup, dashboard, landing page o concepto visual:\n"
            "Debes realizar obligatoriamente una maquetación en HTML5 completa, rica y visualmente impactante entregada dentro de un único bloque de código:\n"
            "```html\n"
            "<!DOCTYPE html>\n"
            "<html lang=\"es\">\n"
            "<head>\n"
            "  <meta charset=\"UTF-8\">\n"
            "  <style>\n"
            "    /* CSS moderno completo: Flexbox/Grid, sombras elegantes, paleta armónica, tipografías y responsive */\n"
            "  </style>\n"
            "</head>\n"
            "<body>\n"
            "  <!-- Estructura HTML5 semántica y visualmente terminada -->\n"
            "  <script>\n"
            "    /* Vanilla JS para interactividad básica si aplica */\n"
            "  </script>\n"
            "</body>\n"
            "</html>\n"
            "```\n"
            "Bajo ningún concepto generes enlaces de imagen ficticios ni intentes generar archivos binarios. La entrega visual debe ser la maquetación HTML5/CSS completa para su previsualización y descarga mediante la herramienta de código."
        )

    @classmethod
    def _build_prompt(
        cls,
        profile: SubAgentProfile,
        user_request: str,
        context_block: str,
        chat_history: list[dict[str, Any]] | None,
        image_provider: str | None,
        team_profiles: Sequence[SubAgentProfile] = (),
    ) -> str:
        parts: list[str] = []
        # 1. Static Shared Prefix (token 0+): session history & RAG context first to maximize provider KV-Cache hits
        chat_history_block = format_chat_history(chat_history)
        if chat_history_block:
            parts.append(chat_history_block)
        if context_block:
            parts.append(context_block)

        # 2. Dynamic Agent Suffix: specialist identity, tools, and phase request
        parts.append(profile.system_prompt)
        if profile.is_supervisor:
            roster_context = format_team_roster(team_profiles, exclude_id=profile.id)
            if roster_context:
                parts.append(roster_context)
        if profile.supports_image_generation:
            parts.append(cls._build_visual_directive(image_provider))
        parts.append(f"## User Request\n{user_request}")
        return "\n\n".join(parts)

    @classmethod
    async def _postprocess_visual_content(
        cls,
        content: str,
        image_provider: str | None,
        image_generator: IImageGenerator | None = None,
    ) -> str:
        if not image_provider or image_generator is None:
            # Strip any stray image generation directives if present without backtracking
            cleaned = re.sub(r"\[GENERATE_IMAGE:[^\]]+\]", "", content)
            return re.sub(r"<!--\s*generate_image:[^-]+-->", "", cleaned)

        # 1. Search for primary explicit directive
        match = re.search(r"\[GENERATE_IMAGE:([^\]]+)\]", content)
        if not match:
            match = re.search(r"<!--\s*generate_image:([^-]+)-->", content)

        if match:
            gen_prompt = match.group(1).strip()
            try:
                _, img_url = await image_generator.generate_and_save(gen_prompt, provider=image_provider)
                clean_alt = re.sub(r"[\r\n]+", " ", gen_prompt)[:45].strip()
                replacement = f"![{clean_alt}]({img_url})"
                return content[:match.start()] + replacement + content[match.end():]
            except Exception as exc:
                warning = f"\n\n> ⚠️ *No se pudo generar la imagen con {image_provider}: {exc}*\n\n"
                return content[:match.start()] + warning + content[match.end():]

        # 2. Fallback: check placeholder markdown image link
        img_match = re.search(r"!\[([^\]]*)\]\(([^)\s]+)\)", content)
        if img_match:
            alt_text = img_match.group(1).strip() or "diseño visual"
            target_url = img_match.group(2)
            if "placeholder" in target_url.lower() or target_url.startswith("http"):
                try:
                    _, img_url = await image_generator.generate_and_save(alt_text, provider=image_provider)
                    return content[:img_match.start()] + f"![{alt_text}]({img_url})" + content[img_match.end():]
                except Exception:
                    logger.warning(
                        "Fallback image generation failed for %s",
                        image_provider,
                        exc_info=True,
                    )

        return content

    @staticmethod
    def _estimate_reusable_context_chars(
        context_block: str,
        chat_history: list[dict[str, Any]] | None,
        user_request: str,
    ) -> int:
        reused = len(context_block) + len(format_chat_history(chat_history))
        shared_stage_markers = (
            "## Formalized Requirements",
            "## Requisitos Formalizados",
            "## Propuesta de ",
            "## Tu propuesta previa",
            "## Architectural Proposals",
            "## Peer Review Critiques",
            "## Critical Evaluation",
            "## User Refinement",
            "Review the following proposals:",
            "The user has selected the following options to review:",
            "Selected Final Solutions:",
            "--- Aportaciones del Consejo ---",
        )
        if any(marker in user_request for marker in shared_stage_markers):
            reused += len(user_request)
        return reused

    @classmethod
    def _calculate_usage(
        cls,
        prompt: str,
        content: str,
        llm_provider: ILLMProvider | None = None,
        *,
        usage: dict[str, int] | None = None,
        reusable_context_chars: int = 0,
    ) -> dict[str, int]:
        resolved: dict[str, int] = dict(usage) if usage is not None else {}
        if usage is None and llm_provider is not None and hasattr(llm_provider, "get_last_usage"):
            resolved = llm_provider.get_last_usage() or {}

        in_tkn = resolved.get("input", 0)
        out_tkn = resolved.get("output", 0)
        if not in_tkn or in_tkn == 0:
            in_tkn = max(15, len(prompt) // 4)
        if not out_tkn or out_tkn == 0:
            out_tkn = max(10, len(content) // 4)

        cached_tkn = resolved.get("cached", 0)
        if not cached_tkn and reusable_context_chars > 0:
            cached_tkn = min(in_tkn, max(1, reusable_context_chars // 4))

        result: dict[str, int] = {"input": in_tkn, "output": out_tkn, "total": in_tkn + out_tkn}
        if cached_tkn > 0:
            result["cached"] = cached_tkn
        return result

    @classmethod
    async def run(
        cls,
        role: str,
        user_request: str,
        llm_provider: ILLMProvider,
        document_store: IDocumentStore,
        model_name: str,
        chat_history: list[dict[str, Any]] | None = None,
        rag_top_k: int | None = None,
        rag_min_score: float | None = None,
        agent_catalog: IAgentCatalogRepository | None = None,
        image_generator: IImageGenerator | None = None,
    ) -> SubAgentResponse:
        """
        Run a sub-agent for the given role (async, ADR-016).

        The ILLMProvider.complete() is synchronous; it is offloaded to a
        thread pool via asyncio.to_thread() to avoid blocking the event loop.
        """
        if agent_catalog is None:
            raise ValueError("agent_catalog must be provided to SubAgentRunner.run()")
        profile = agent_catalog.get_profile(role)
        context_chunks, context_block = await asyncio.to_thread(
            cls._retrieve_rag_context,
            profile,
            user_request,
            document_store,
            rag_top_k=rag_top_k,
            rag_min_score=rag_min_score,
        )
        image_provider = image_generator.get_provider_name() if image_generator is not None else None
        team_profiles = agent_catalog.get_all_profiles() if profile.is_supervisor else ()
        prompt = cls._build_prompt(
            profile,
            user_request,
            context_block,
            chat_history,
            image_provider,
            team_profiles=team_profiles,
        )

        start_time = time.perf_counter()
        content, raw_usage = await asyncio.to_thread(
            invoke_llm_with_usage, llm_provider, prompt, model_name
        )
        latency = round(time.perf_counter() - start_time, 2)

        if profile.supports_image_generation:
            content = await cls._postprocess_visual_content(
                content,
                image_provider,
                image_generator=image_generator,
            )

        reusable_chars = cls._estimate_reusable_context_chars(
            context_block,
            chat_history,
            user_request,
        )
        usage = cls._calculate_usage(
            prompt,
            content,
            llm_provider,
            usage=raw_usage,
            reusable_context_chars=reusable_chars,
        )

        return SubAgentResponse(
            role=role,
            content=content,
            context_chunks=context_chunks,
            tokens=usage,
            latency=latency,
            model_name=model_name,
        )

