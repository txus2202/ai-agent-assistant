"""
Presentation WS Coordinator: DebateLearningCoordinator

Handles knowledge ingestion directives, pending tag/domain prompts, and attachment
cleanup on behalf of DebateWebSocketHandler without bloating transport coordination.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from src.application.services.learn_from_source import LearnFromSource, SourceType
from src.domain.agents.supervisor_events import EventType, SupervisorEvent
from src.domain.ports.document_parser import IDocumentParser
from src.domain.ports.document_store import IDocumentStore
from src.domain.ports.llm_provider import ILLMProvider
from src.domain.ports.source_extractor import ISourceExtractor
from src.presentation.api.routes.upload import resolve_user_attachment_path
from src.presentation.api.ws.learning_command_parser import (
    LEARN_DIRECTIVE_REGEX,
    detect_source_type,
    extract_domain,
    extract_tags,
    find_pending_learning_in_events,
    is_http_url,
    resolve_pending_tags,
)

logger = logging.getLogger(__name__)

_ASK_TAGS_AND_DOMAIN_MSG = (
    "He recibido este conocimiento para asimilarlo. "
    "Antes de sellarlo e integrarlo en el Vault, ¿deseas catalogarlo con algún tag o etiqueta específico "
    "(por ejemplo: `#seguridad`, `#pubsub`), o en qué dominio deseas catalogarlo?\n\n"
    "- 🏢 **Arquitectura Empresarial** (`01_enterprise_architecture`): Estándares corporativos y directrices oficiales.\n"
    "- 🔬 **Investigación Externa** (`learned`): Artículos, tutoriales o whitepapers externos.\n"
    "- 🛠️ **Plataforma & TFM** (`00_meta_project`): Documentación interna y especificaciones del sistema.\n\n"
    "También puedes solicitar crear un nuevo dominio si este contenido pertenece a una nueva área."
)


class DebateLearningCoordinator:
    """Coordinates WebSocket learning ingestion and interactive metadata prompting."""

    def __init__(
        self,
        *,
        send_event: Callable[[SupervisorEvent], Awaitable[None]],
        get_doc_store: Callable[[], Awaitable[IDocumentStore]],
        resolve_learning_llm_sync: Callable[[Any], tuple[ILLMProvider, str]],
        vault_root: Path,
        source_extractors: dict[SourceType, ISourceExtractor],
        document_parser: IDocumentParser,
        get_user_id: Callable[[], str | None],
        get_debate_events: Callable[[], list[dict[str, Any]] | None],
        fallback_sub_agent: Callable[[str, str, list[Any]], Awaitable[Any]],
    ) -> None:
        self._send_event = send_event
        self._get_doc_store = get_doc_store
        self._resolve_learning_llm_sync = resolve_learning_llm_sync
        self._vault_root = vault_root
        self._source_extractors = source_extractors
        self._document_parser = document_parser
        self._get_user_id = get_user_id
        self._get_debate_events = get_debate_events
        self._fallback_sub_agent = fallback_sub_agent

    async def _learn_single_attachment(
        self,
        attachment_path: str,
        tags: list[str],
        tag_suffix: str,
        llm_prov: ILLMProvider,
        mod_name: str,
        target_domain: str = "learned",
    ) -> str:
        temp_file_to_delete: Path | None = None
        if is_http_url(attachment_path):
            source_arg = attachment_path.strip()
            stype = SourceType.URL
            display_name = source_arg
        else:
            user_id = self._get_user_id()
            try:
                safe_path = resolve_user_attachment_path(attachment_path, user_id)
            except (ValueError, PermissionError):
                logger.warning("Blocked unsafe attachment path for user %s", user_id)
                return "❌ Ruta de archivo adjunto no permitida."
            if not safe_path.is_file():
                return f"❌ El archivo adjunto '{safe_path.name}' no existe o ha expirado."
            source_arg = str(safe_path)
            stype = detect_source_type(source_arg)
            temp_file_to_delete = safe_path
            display_name = safe_path.name

        doc_store = await self._get_doc_store()
        try:
            res = await asyncio.to_thread(
                LearnFromSource.run,
                source=source_arg,
                source_type=stype,
                llm_provider=llm_prov,
                document_store=doc_store,
                vault_root=self._vault_root,
                model_name=mod_name,
                tags=tags,
                target_domain=target_domain,
                extractors=self._source_extractors,
                document_parser=self._document_parser,
            )
        finally:
            if temp_file_to_delete is not None:
                try:
                    await asyncio.to_thread(temp_file_to_delete.unlink, missing_ok=True)
                except OSError:
                    logger.warning("Failed to remove temporary attachment %s", temp_file_to_delete, exc_info=True)

        if res.errors:
            return f"❌ Error al procesar {display_name}: {res.errors}"
        file_name = res.generated_file.name if res.generated_file else "nota"
        dom_msg = f" en [{target_domain}]" if target_domain != "learned" else ""
        return f"✅ Conocimiento asimilado{dom_msg} desde {display_name}. Generada nota: {file_name}{tag_suffix}"

    async def _learn_single_text(
        self,
        text_to_learn: str,
        tags: list[str],
        tag_suffix: str,
        llm_prov: ILLMProvider,
        mod_name: str,
        target_domain: str = "learned",
    ) -> str:
        doc_store = await self._get_doc_store()
        res = await asyncio.to_thread(
            LearnFromSource.run,
            source=text_to_learn,
            source_type=SourceType.TEXT,
            llm_provider=llm_prov,
            document_store=doc_store,
            vault_root=self._vault_root,
            model_name=mod_name,
            tags=tags,
            target_domain=target_domain,
            extractors=self._source_extractors,
            document_parser=self._document_parser,
        )
        if res.errors:
            return f"❌ Error al aprender el texto: {res.errors}"
        file_name = res.generated_file.name if res.generated_file else "nota"
        dom_msg = f" en [{target_domain}]" if target_domain != "learned" else ""
        return f"✅ He asimilado y guardado este conocimiento{dom_msg} en mi memoria persistente y en el Vault ({file_name}){tag_suffix}."

    async def _execute_ingest(
        self,
        text_to_learn: str,
        attachments: list[str],
        tags: list[str],
        llm_prov: ILLMProvider,
        mod_name: str,
        target_domain: str = "learned",
    ) -> list[str]:
        tag_suffix = f" [tags: {', '.join(tags)}]" if tags else ""
        if attachments:
            return [
                await self._learn_single_attachment(path, tags, tag_suffix, llm_prov, mod_name, target_domain=target_domain)
                for path in attachments
            ]
        if text_to_learn:
            return [await self._learn_single_text(text_to_learn, tags, tag_suffix, llm_prov, mod_name, target_domain=target_domain)]
        return []

    async def _emit_completion(
        self,
        learn_role: str,
        content: str,
        mod_name: str,
        extra_meta: dict[str, Any] | None = None,
    ) -> None:
        meta = {"model": mod_name, **(extra_meta or {})}
        await self._send_event(SupervisorEvent(
            type=EventType.AGENT_COMPLETED, role=learn_role, content=content, metadata=meta
        ))
        await self._send_event(SupervisorEvent(
            type=EventType.DONE,
            role=learn_role,
            content=content,
            metadata={**meta, "metrics_reported": "true"},
        ))

    async def handle_learning(
        self,
        learn_profile: Any,
        user_request: str,
        attachments: list[str],
        directive_match: re.Match[str] | None = None,
        target_domain: str | None = None,
    ) -> None:
        learn_role = learn_profile.display_name
        await self._send_event(SupervisorEvent(type=EventType.AGENT_STARTED, role=learn_role, content=""))

        llm_prov, mod_name = await asyncio.to_thread(self._resolve_learning_llm_sync, learn_profile)
        extracted_tags = extract_tags(user_request)
        resolved_domain = target_domain or extract_domain(user_request)
        text_to_learn = directive_match.group(1).strip() if directive_match else user_request.strip()

        if not extracted_tags and not resolved_domain:
            pending_json = json.dumps({
                "text": text_to_learn,
                "attachments": attachments,
                "target_domain": target_domain,
            })
            await self._emit_completion(
                learn_role,
                _ASK_TAGS_AND_DOMAIN_MSG,
                mod_name,
                extra_meta={"pending_learning": pending_json},
            )
            return

        results = await self._execute_ingest(
            text_to_learn=text_to_learn,
            attachments=attachments,
            tags=extracted_tags,
            llm_prov=llm_prov,
            mod_name=mod_name,
            target_domain=resolved_domain or "learned",
        )
        content = "\n".join(results) or "No se proporcionó contenido para el aprendizaje."
        await self._emit_completion(learn_role, content, mod_name)

    async def handle_pending_learning(
        self,
        learn_profile: Any,
        user_request: str,
        pending_learning: dict[str, Any],
    ) -> None:
        learn_role = learn_profile.display_name
        await self._send_event(SupervisorEvent(type=EventType.AGENT_STARTED, role=learn_role, content=""))

        llm_prov, mod_name = await asyncio.to_thread(self._resolve_learning_llm_sync, learn_profile)
        target_domain = extract_domain(user_request) or pending_learning.get("target_domain") or "learned"
        tags = resolve_pending_tags(user_request)

        results = await self._execute_ingest(
            text_to_learn=pending_learning.get("text", ""),
            attachments=pending_learning.get("attachments", []),
            tags=tags,
            llm_prov=llm_prov,
            mod_name=mod_name,
            target_domain=target_domain,
        )
        content = "\n".join(results) or "No se proporcionó contenido para el aprendizaje."
        await self._emit_completion(learn_role, content, mod_name)

    async def dispatch(
        self,
        target_profile: Any,
        target_agent: str,
        user_request: str,
        chat_history: list[Any],
        attachments: list[str],
        target_domain: str | None = None,
    ) -> None:
        directive_match = LEARN_DIRECTIVE_REGEX.match(user_request.strip()) if user_request else None
        events = self._get_debate_events()
        pending_learning = find_pending_learning_in_events(events) if (not directive_match and events) else None

        if pending_learning:
            await self.handle_pending_learning(target_profile, user_request, pending_learning)
        elif attachments or directive_match or target_domain:
            await self.handle_learning(target_profile, user_request, attachments, directive_match, target_domain=target_domain)
        else:
            await self._fallback_sub_agent(target_agent, user_request, chat_history)

