"""
Presentation: WS Debate Route

WebSocket endpoint for streaming the multi-agent debate and handling
real-time HITL decisions (ADR-016).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any, Iterable

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.application.agents.sub_agent_runner import SubAgentRunner
from src.application.agents.supervisor_agent import SupervisorAgent
from src.application.services.learn_from_source import LearnFromSource, SourceType
from src.domain.agents.sub_agent_profiles import get_profile
from src.domain.agents.supervisor_events import HITLResponse, SupervisorEvent, EventType, HITLDecision
from src.domain.ports.observability_port import TraceContext, SpanContext
from src.domain.value_objects.debate_record import DebateRecord
from src.infrastructure.llm.registry import get_llm_provider
from src.infrastructure.persistence.sqlite_agent_config_repository import SqliteAgentConfigRepository
from src.infrastructure.persistence.sqlite_debate_repository import SqliteDebateRepository
from src.infrastructure.rag.chroma_document_store import ChromaDBDocumentStore
from src.presentation.api.config import get_settings
from src.presentation.api.routes.observability import get_observability_service
from src.presentation.api.ws.serializers import dict_to_hitl_response, event_to_dict

router = APIRouter(tags=["debate"])
logger = logging.getLogger(__name__)

LEARN_DIRECTIVE_REGEX = re.compile(
    r"^(?:/learn|aprende\s+esto|aprende|memoriza|guarda\s+este\s+conocimiento)[:\s]+(.+)",
    re.IGNORECASE | re.DOTALL,
)

BRACKET_TAGS_REGEX = re.compile(
    r"\[(?:tag|etiqueta)s?:\s*([^\s\]][^\]\r\n]*)\]",
    re.IGNORECASE,
)

NL_TAGS_REGEX = re.compile(
    r"\b(?:con\s+(?:(?:los|las)\s+)?)?(?:tag|etiqueta)s?:\s*([^\s#\[\]][^#\r\n\[\]]*)",
    re.IGNORECASE,
)

HASHTAGS_REGEX = re.compile(
    r"(?<!\S)#([a-zA-Z0-9_\-\.]+)",
)


def _detect_source_type(source: str) -> SourceType:
    lower = source.lower()
    if lower.startswith(("http://", "https://")):
        return SourceType.URL
    if lower.endswith(".pdf"):
        return SourceType.PDF
    if lower.endswith((".md", ".markdown")):
        return SourceType.MARKDOWN
    if lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return SourceType.IMAGE
    return SourceType.PDF


def _append_unique_tags(target: list[str], candidates: Iterable[str]) -> None:
    for item in candidates:
        clean = item.strip().lstrip("#")
        if clean and clean not in target and not clean.startswith(("http://", "https://")):
            target.append(clean)


def _extract_bracket_tags(text: str) -> list[str]:
    match = BRACKET_TAGS_REGEX.search(text)
    return match.group(1).split(",") if match else []


def _extract_nl_tags(text: str) -> list[str]:
    match = NL_TAGS_REGEX.search(text)
    return match.group(1).split(",") if match else []


def _extract_hashtags(text: str) -> list[str]:
    return HASHTAGS_REGEX.findall(text)


def _extract_tags(text: str) -> list[str]:
    tags: list[str] = []
    _append_unique_tags(tags, _extract_bracket_tags(text))
    _append_unique_tags(tags, _extract_nl_tags(text))
    _append_unique_tags(tags, _extract_hashtags(text))
    return tags


def _extract_domain(text: str) -> str | None:
    low = text.lower()
    if any(k in low for k in ("enterprise", "empresa", "corporativ", "estándar", "estandar", "01_enterprise")):
        return "01_enterprise_architecture"
    if any(k in low for k in ("tfm", "plataforma", "meta_project", "00_meta")):
        return "00_meta_project"
    if any(k in low for k in ("deliberation", "deliberación", "acta", "sesion", "sesión")):
        return "deliberations/sessions"
    if any(k in low for k in ("investigacion", "investigación", "learned", "externo", "whitepaper")):
        return "learned"
    return None


def _is_skip_tags_response(text: str) -> bool:
    low = text.strip().lower()
    return low in (
        "sin tags", "sin tag", "sin etiquetas", "sin etiqueta",
        "no", "ninguno", "ninguna", "asímilalo directamente", "asimilalo directamente",
        "directamente", "adelante", "omitir", "ningun tag", "ninguna etiqueta", "no gracias"
    ) or low.startswith(("sin tag", "sin etiqueta", "asimil", "adelante"))


def _parse_pending_learning_payload(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None
    return None


def _extract_pending_from_event(ev: dict[str, Any]) -> dict[str, Any] | None:
    if ev.get("type") not in ("agent_completed", "done"):
        return None
    meta = ev.get("metadata")
    if not isinstance(meta, dict):
        return None
    return _parse_pending_learning_payload(meta.get("pending_learning"))


class DebateWebSocketHandler:
    """Handles the WebSocket debate streaming and HITL responses."""
    
    def __init__(self, websocket: WebSocket, authenticated_user: Any = None, auth_service: Any = None):
        self.websocket = websocket
        self.authenticated_user = authenticated_user
        self.auth_service = auth_service
        self.settings = get_settings()
        db_path = str(self.settings.sqlite_db_path)
        from src.infrastructure.persistence.sqlite_agent_config_repository import UserScopedAgentConfigRepository
        base_agent_repo = SqliteAgentConfigRepository(db_path)
        user_id_scope = self.authenticated_user.id if self.authenticated_user else None
        self.agent_config_repo = UserScopedAgentConfigRepository(base_agent_repo, user_id=user_id_scope)
        self.debate_repo = SqliteDebateRepository(db_path)
        store_kwargs: dict[str, Any] = {}
        if self.settings.chroma_host:
            store_kwargs["host"] = self.settings.chroma_host
            store_kwargs["port"] = self.settings.chroma_port
        self.document_store = ChromaDBDocumentStore(
            persist_directory=str(self.settings.chroma_persist_dir),
            **store_kwargs,
        )
        self.debate_record: DebateRecord | None = None
        self.observability = get_observability_service()
        self.current_trace: TraceContext | None = None
        self.active_spans: dict[str, SpanContext] = {}

    def _persist_event(self, event_dict: dict[str, Any], event: SupervisorEvent) -> None:
        if not self.debate_record or event.type == EventType.STREAM_CHUNK:
            return
        self.debate_repo.append_event(self.debate_record.id, json.dumps(event_dict))
        if event.type == EventType.DONE:
            self.debate_repo.update_status(self.debate_record.id, "completed")

    def _on_agent_started(self, event: SupervisorEvent) -> None:
        if not (self.current_trace and event.role):
            return
        role_val = event.role.value if hasattr(event.role, "value") else str(event.role)
        config = self.agent_config_repo.find_by_role(role_val)
        default_mod = ""
        try:
            profile = get_profile(role_val)
            default_mod = getattr(profile, "default_model", "")
        except KeyError:
            pass
        model_name = config.model_name if (config and config.model_name) else (default_mod or self.settings.default_model)
        input_prompt = self.debate_record.user_request if self.debate_record else ""
        self.active_spans[role_val] = self.observability.start_agent_span(
            trace_context=self.current_trace,
            agent_role=role_val,
            input_prompt=input_prompt,
            metadata={"phase": "debate", "model": model_name},
            model_name=model_name,
        )

    def _on_agent_completed(self, event: SupervisorEvent) -> None:
        if not (self.current_trace and event.role):
            return
        role_val = event.role.value if hasattr(event.role, "value") else str(event.role)
        span = self.active_spans.pop(role_val, None)
        if not span:
            return
        meta = event.metadata or {}
        latency = float(meta.get("latency_seconds", 0.0))
        token_counts = {
            "input": int(meta.get("prompt_tokens", 0)),
            "output": int(meta.get("completion_tokens", 0)),
            "total": int(meta.get("total_tokens", meta.get("tokens", 0))),
        }
        model_name = meta.get("model") or getattr(span, "model_name", None)
        self.observability.end_agent_span(
            span_context=span,
            output=event.content,
            token_counts=token_counts,
            latency=latency,
            status="SUCCESS",
            model_name=model_name,
        )

    def _on_debate_done(self, event: SupervisorEvent) -> None:
        if not self.current_trace:
            return
        self.observability.end_trace(
            trace_context=self.current_trace,
            status="SUCCESS",
            output=event.content,
        )
        self.current_trace = None

    def _track_event_observability(self, event: SupervisorEvent) -> None:
        if not self.current_trace:
            return
        if event.type == EventType.AGENT_STARTED:
            self._on_agent_started(event)
        elif event.type == EventType.AGENT_COMPLETED:
            self._on_agent_completed(event)
        elif event.type == EventType.DONE:
            self._on_debate_done(event)

    async def send_event(self, event: SupervisorEvent) -> None:
        """Helper to send event to WS, append to SQLite, and stream observability spans."""
        event_dict = event_to_dict(event)
        if self.current_trace:
            if "metadata" not in event_dict or not isinstance(event_dict["metadata"], dict):
                event_dict["metadata"] = {}
            event_dict["metadata"]["trace_id"] = self.current_trace.trace_id
        await self.websocket.send_json(event_dict)
        self._persist_event(event_dict, event)
        self._track_event_observability(event)


    async def hitl_callback(self, event: SupervisorEvent) -> HITLResponse:
        """
        Pause debate execution and await client response for the HITL checkpoint.
        (The HITL_REQUIRED event itself was already yielded by the generator and sent).
        """
        raw_resp = await self.websocket.receive_json()
        hitl_resp = dict_to_hitl_response(raw_resp)

        if self.current_trace:
            decision_val = (
                hitl_resp.decision.value
                if hasattr(hitl_resp.decision, "value")
                else str(hitl_resp.decision)
            )
            score_map = {
                HITLDecision.APPROVE: 1.0,
                HITLDecision.REFINE: 0.5,
                HITLDecision.DIVERT: 0.5,
                HITLDecision.FINISH: 1.0,
                HITLDecision.REJECT: 0.0,
            }
            score_val = score_map.get(hitl_resp.decision, 0.5)
            self.observability.score_trace(
                trace_context=self.current_trace,
                name="hitl_decision",
                value=score_val,
                comment=f"Decision: {decision_val}. Feedback: {hitl_resp.feedback or 'None'}",
            )

        if hitl_resp.decision == HITLDecision.REFINE and hitl_resp.feedback and self.debate_record:
            refine_event_dict = {
                "type": "user_message",
                "role": "user",
                "content": hitl_resp.feedback,
                "metadata": {"decision": "refine", "target_agents": hitl_resp.target_agents}
            }
            self.debate_repo.append_event(self.debate_record.id, json.dumps(refine_event_dict))
        try:
            from src.presentation.api.ws.wake_word import wake_word_service
            wake_word_service.reset()
        except Exception:
            pass
        return hitl_resp

    async def _handle_supervisor(self, user_request: str, chat_history: list[dict[str, Any]] | None = None) -> None:
        try:
            async for event in SupervisorAgent.run(
                user_request=user_request,
                document_store=self.document_store,
                agent_config_repo=self.agent_config_repo,
                llm_factory=get_llm_provider,
                hitl_callback=self.hitl_callback,
                chat_history=chat_history,
            ):
                await self.send_event(event)
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected during supervisor debate; aborting")
            self.abort()
            raise
        except Exception as e:
            logger.exception("Error during supervisor debate execution")
            if self.debate_record:
                self.debate_repo.update_status(self.debate_record.id, "error")
            if self.current_trace:
                try:
                    self.observability.end_trace(
                        trace_context=self.current_trace,
                        status="ERROR",
                        output=str(e),
                    )
                except Exception:
                    pass
                self.current_trace = None
            await self.send_event(SupervisorEvent(
                type=EventType.ERROR, role="supervisor", content=str(e)
            ))
        finally:
            try:
                from src.presentation.api.ws.wake_word import wake_word_service
                wake_word_service.reset()
            except Exception:
                pass

    def _get_pending_learning(self) -> dict[str, Any] | None:
        if not self.debate_record or not self.debate_record.events:
            return None
        for ev in reversed(self.debate_record.events):
            pending = _extract_pending_from_event(ev)
            if pending:
                return pending
            if ev.get("type") != "user_message":
                break
        return None

    async def _learn_single_attachment(
        self,
        attachment_path: str,
        tags: list[str],
        tag_suffix: str,
        llm_prov: Any,
        mod_name: str,
        target_domain: str = "learned",
    ) -> str:
        stype = _detect_source_type(attachment_path)
        res = await asyncio.to_thread(
            LearnFromSource.run,
            source=attachment_path,
            source_type=stype,
            llm_provider=llm_prov,
            document_store=self.document_store,
            vault_root=self.settings.vault_root,
            model_name=mod_name,
            tags=tags,
            target_domain=target_domain,
        )
        if res.errors:
            return f"❌ Error al procesar {attachment_path}: {res.errors}"
        file_name = res.generated_file.name if res.generated_file else "nota"
        dom_msg = f" en [{target_domain}]" if target_domain != "learned" else ""
        return f"✅ Conocimiento asimilado{dom_msg} desde {attachment_path}. Generada nota: {file_name}{tag_suffix}"

    async def _learn_single_text(
        self,
        text_to_learn: str,
        tags: list[str],
        tag_suffix: str,
        llm_prov: Any,
        mod_name: str,
        target_domain: str = "learned",
    ) -> str:
        res = await asyncio.to_thread(
            LearnFromSource.run,
            source=text_to_learn,
            source_type=SourceType.TEXT,
            llm_provider=llm_prov,
            document_store=self.document_store,
            vault_root=self.settings.vault_root,
            model_name=mod_name,
            tags=tags,
            target_domain=target_domain,
        )
        if res.errors:
            return f"❌ Error al aprender el texto: {res.errors}"
        file_name = res.generated_file.name if res.generated_file else "nota"
        dom_msg = f" en [{target_domain}]" if target_domain != "learned" else ""
        return f"✅ He asimilado y guardado este conocimiento{dom_msg} en mi memoria persistente y en el Vault ({file_name}){tag_suffix}."

    async def _execute_learning_ingest(
        self,
        text_to_learn: str,
        attachments: list[str],
        tags: list[str],
        llm_prov: Any,
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

    async def _handle_learning(
        self,
        learn_profile: Any,
        user_request: str,
        attachments: list[str],
        directive_match: re.Match[str] | None = None,
        target_domain: str | None = None,
    ) -> None:
        learn_role = learn_profile.display_name
        yield_event = SupervisorEvent(type=EventType.AGENT_STARTED, role=learn_role, content="")
        await self.send_event(yield_event)
        
        config = self.agent_config_repo.find_by_role(learn_profile.id)
        if not config:
            config = self.agent_config_repo.find_by_role(learn_role)
        prov_name = config.provider if config else self.settings.default_provider
        mod_name = config.model_name if config else self.settings.default_model
        llm_prov = get_llm_provider(prov_name)
        
        extracted_tags = _extract_tags(user_request)
        resolved_domain = target_domain or _extract_domain(user_request)
        text_to_learn = directive_match.group(1).strip() if directive_match else user_request.strip()

        # If user did NOT specify tags or domain, prompt them first
        if not extracted_tags and not resolved_domain:
            ask_content = (
                "He recibido este conocimiento para asimilarlo. "
                "Antes de sellarlo e integrarlo en el Vault, ¿deseas catalogarlo con algún tag o etiqueta específico "
                "(por ejemplo: `#seguridad`, `#pubsub`), o en qué dominio deseas catalogarlo?\n\n"
                "- 🏢 **Arquitectura Empresarial** (`01_enterprise_architecture`): Estándares corporativos y directrices oficiales.\n"
                "- 🔬 **Investigación Externa** (`learned`): Artículos, tutoriales o whitepapers externos.\n"
                "- 🛠️ **Plataforma & TFM** (`00_meta_project`): Documentación interna y especificaciones del sistema.\n\n"
                "También puedes solicitar crear un nuevo dominio si este contenido pertenece a una nueva área."
            )
            learn_meta = {
                "model": mod_name,
                "pending_learning": json.dumps({
                    "text": text_to_learn,
                    "attachments": attachments,
                    "target_domain": target_domain,
                }),
            }
            await self.send_event(SupervisorEvent(
                type=EventType.AGENT_COMPLETED, role=learn_role, content=ask_content, metadata=learn_meta
            ))
            await self.send_event(SupervisorEvent(
                type=EventType.DONE, role=learn_role, content=ask_content, metadata=learn_meta
            ))
            return

        domain_to_use = resolved_domain or "learned"
        results = await self._execute_learning_ingest(
            text_to_learn=text_to_learn,
            attachments=attachments,
            tags=extracted_tags,
            llm_prov=llm_prov,
            mod_name=mod_name,
            target_domain=domain_to_use,
        )
        content = "\n".join(results) or "No se proporcionó contenido para el aprendizaje."
        learn_meta = {"model": mod_name}
        await self.send_event(SupervisorEvent(
            type=EventType.AGENT_COMPLETED, role=learn_role, content=content, metadata=learn_meta
        ))
        await self.send_event(SupervisorEvent(
            type=EventType.DONE, role=learn_role, content=content, metadata=learn_meta
        ))

    async def _handle_pending_learning(
        self,
        learn_profile: Any,
        user_request: str,
        pending_learning: dict[str, Any],
    ) -> None:
        learn_role = learn_profile.display_name
        yield_event = SupervisorEvent(type=EventType.AGENT_STARTED, role=learn_role, content="")
        await self.send_event(yield_event)
        
        config = self.agent_config_repo.find_by_role(learn_profile.id)
        if not config:
            config = self.agent_config_repo.find_by_role(learn_role)
        prov_name = config.provider if config else self.settings.default_provider
        mod_name = config.model_name if config else self.settings.default_model
        llm_prov = get_llm_provider(prov_name)
        
        target_domain = (
            _extract_domain(user_request)
            or pending_learning.get("target_domain")
            or "learned"
        )
        tags: list[str] = []
        if not _is_skip_tags_response(user_request):
            tags = _extract_tags(user_request)
            if not tags and not _extract_domain(user_request):
                tags = [
                    t.strip().lstrip("#")
                    for t in re.split(r"[,;]", user_request)
                    if t.strip() and len(t.strip()) < 30
                ]

        text_to_learn = pending_learning.get("text", "")
        attachments = pending_learning.get("attachments", [])

        results = await self._execute_learning_ingest(
            text_to_learn=text_to_learn,
            attachments=attachments,
            tags=tags,
            llm_prov=llm_prov,
            mod_name=mod_name,
            target_domain=target_domain,
        )
        content = "\n".join(results) or "No se proporcionó contenido para el aprendizaje."
        learn_meta = {"model": mod_name}
        await self.send_event(SupervisorEvent(
            type=EventType.AGENT_COMPLETED, role=learn_role, content=content, metadata=learn_meta
        ))
        await self.send_event(SupervisorEvent(
            type=EventType.DONE, role=learn_role, content=content, metadata=learn_meta
        ))

    def _resolve_agent_llm(self, profile: SubAgentProfile, agent_role: str) -> tuple[ILLMProvider, str]:
        config = self.agent_config_repo.find_by_role(profile.id)
        if not config:
            config = self.agent_config_repo.find_by_role(agent_role)
        default_prov = getattr(profile, "default_provider", "") or self.settings.default_provider
        default_mod = getattr(profile, "default_model", "") or self.settings.default_model
        prov_name = config.provider if (config and config.provider) else default_prov
        mod_name = config.model_name if (config and config.model_name) else default_mod
        return get_llm_provider(prov_name), mod_name

    async def _emit_sub_agent_completion(
        self, agent_role: str, resp: SubAgentResponse, mod_name: str, emit_message: bool, emit_done: bool
    ) -> None:
        sub_meta = {
            "model": resp.model_name or mod_name,
            "prompt_tokens": str(resp.tokens.get("input", 0)),
            "completion_tokens": str(resp.tokens.get("output", 0)),
            "total_tokens": str(resp.tokens.get("total", 0)),
            "latency_seconds": str(resp.latency),
            "tokens": str(resp.tokens.get("total", 0)),
        }
        if emit_message:
            await self.send_event(SupervisorEvent(
                type=EventType.MESSAGE, role=agent_role, content=resp.content
            ))
        await self.send_event(SupervisorEvent(
            type=EventType.AGENT_COMPLETED, role=agent_role, content=resp.content, metadata=sub_meta
        ))
        if emit_done:
            await self.send_event(SupervisorEvent(
                type=EventType.DONE, role=agent_role, content=resp.content, metadata=sub_meta
            ))

    async def _handle_sub_agent_exception(self, agent_role: str, exc: Exception) -> None:
        logger.exception("Error during sub-agent execution: %s", agent_role)
        if self.debate_record:
            self.debate_repo.update_status(self.debate_record.id, "error")
        if self.current_trace:
            try:
                self.observability.end_trace(
                    trace_context=self.current_trace,
                    status="ERROR",
                    output=str(exc),
                )
            except Exception:
                pass
            self.current_trace = None
        await self.send_event(SupervisorEvent(
            type=EventType.ERROR, role=agent_role, content=str(exc)
        ))

    async def _handle_sub_agent(
        self,
        target_agent: str,
        user_request: str,
        chat_history: list[dict[str, Any]] | None = None,
        emit_done: bool = True,
        emit_message: bool = False,
    ) -> str | None:
        agent_role = target_agent
        try:
            profile = get_profile(target_agent)
            agent_role = profile.display_name
            await self.send_event(SupervisorEvent(
                type=EventType.AGENT_STARTED, role=agent_role, content=""
            ))

            llm_prov, mod_name = self._resolve_agent_llm(profile, agent_role)
            config = self.agent_config_repo.find_by_role(profile.id) or self.agent_config_repo.find_by_role(agent_role)
            runner_kwargs: dict[str, Any] = {"chat_history": chat_history} if chat_history else {}
            if config and getattr(config, "rag_top_k", None) is not None:
                runner_kwargs["rag_top_k"] = config.rag_top_k
            if config and getattr(config, "rag_min_score", None) is not None:
                runner_kwargs["rag_min_score"] = config.rag_min_score
            resp = await SubAgentRunner.run(
                role=agent_role,
                user_request=user_request,
                llm_provider=llm_prov,
                document_store=self.document_store,
                model_name=mod_name,
                **runner_kwargs,
            )

            await self._emit_sub_agent_completion(agent_role, resp, mod_name, emit_message, emit_done)
            return resp.content

        except KeyError:
            if self.debate_record:
                self.debate_repo.update_status(self.debate_record.id, "aborted")
            await self.websocket.send_json({"type": "error", "content": f"Unknown agent role: {target_agent}"})
            await self.websocket.close(code=1003)
            return None
        except Exception as e:
            await self._handle_sub_agent_exception(agent_role, e)
            return None

    @staticmethod
    def _build_trace_tags(target_agent: str, attachments: list[Any] | None = None) -> list[str]:
        tags = [f"agent:{target_agent}"]
        try:
            profile = get_profile(target_agent)
            flow_tag = "flow:supervisor_debate" if profile.is_supervisor else "flow:sub_agent"
            tags.append(flow_tag)
            if profile.supports_hitl:
                tags.append("has:hitl")
            if profile.uses_rag or profile.can_ingest_documents:
                tags.append("has:rag")
        except KeyError:
            tags.append("flow:sub_agent")

        if attachments:
            tags.append("has:attachments")
        return tags

    def _init_session_and_trace(
        self,
        session_id: str | None,
        user_request: str,
        target_agent: str,
        user_id: str | None = None,
        attachments: list[Any] | None = None,
    ) -> None:
        user_id_scope = self.authenticated_user.id if self.authenticated_user else None
        existing_record = self.debate_repo.find_by_id(session_id, user_id=user_id_scope) if session_id else None

        if session_id and not existing_record:
            # Check if this session exists under another user to prevent IDOR hijacking
            unfiltered_check = self.debate_repo.find_by_id(session_id, allow_unscoped=True)
            if unfiltered_check:
                raise PermissionError(f"Access denied: Session '{session_id}' belongs to another user")

        if existing_record:
            self.debate_record = existing_record
            self.debate_record.target_agent = target_agent
            self.debate_repo.update_session(self.debate_record.id, status="running", target_agent=target_agent)
        else:
            self.debate_record = DebateRecord(
                id=session_id or str(uuid.uuid4()),
                user_request=user_request,
                target_agent=target_agent,
                status="running",
                user_id=user_id_scope,
            )
            self.debate_repo.create(self.debate_record)

        # Persist user message in chronological event history
        user_event_dict = {
            "type": "user_message",
            "role": "user",
            "content": user_request,
            "metadata": {"target_agent": target_agent}
        }
        self.debate_repo.append_event(self.debate_record.id, json.dumps(user_event_dict))

        tags = self._build_trace_tags(target_agent, attachments)
        effective_user = (
            self.authenticated_user.username if self.authenticated_user else user_id
        ) or getattr(self.settings, "langfuse_default_user_id", "local_user")

        self.current_trace = self.observability.start_trace(
            name=f"debate_{target_agent}",
            session_id=self.debate_record.id,
            user_id=effective_user,
            input_data=user_request,
            tags=tags,
            metadata={
                "target_agent": target_agent,
            }
        )

    async def _dispatch_ingestion_target(
        self,
        target_profile: Any,
        target_agent: str,
        user_request: str,
        chat_history: list,
        attachments: list,
        target_domain: str | None = None,
    ) -> None:
        directive_match = LEARN_DIRECTIVE_REGEX.match(user_request.strip()) if user_request else None
        pending_learning = self._get_pending_learning() if not directive_match else None
        if pending_learning:
            await self._handle_pending_learning(target_profile, user_request, pending_learning)
        elif attachments or directive_match or target_domain:
            await self._handle_learning(target_profile, user_request, attachments, directive_match, target_domain=target_domain)
        else:
            await self._handle_sub_agent(target_agent, user_request, chat_history=chat_history)

    async def _dispatch_target(
        self,
        target_agent: str,
        user_request: str,
        chat_history: list,
        attachments: list,
        target_domain: str | None = None,
    ) -> bool:
        try:
            target_profile = get_profile(target_agent)
        except KeyError:
            if self.debate_record:
                self.debate_repo.update_status(self.debate_record.id, "aborted")
            await self.websocket.send_json({"type": "error", "content": f"Unknown agent role: {target_agent}"})
            await self.websocket.close(code=1003)
            return False

        if target_profile.is_supervisor:
            await self._handle_supervisor(user_request, chat_history=chat_history)
        elif target_profile.can_ingest_documents:
            await self._dispatch_ingestion_target(
                target_profile, target_agent, user_request, chat_history, attachments, target_domain=target_domain
            )
        else:
            await self._handle_sub_agent(target_agent, user_request, chat_history=chat_history)
        return True

    @staticmethod
    def _extract_target_agents(raw_start: dict) -> list[str]:
        target_agents = raw_start.get("target_agents", [])
        if target_agents:
            return list(target_agents)
        target_agent = raw_start.get("target_agent", "supervisor")
        return [target_agent] if isinstance(target_agent, str) else list(target_agent)

    @staticmethod
    def _resolve_agent_display_name(agent_id: str) -> str:
        try:
            return get_profile(agent_id).display_name
        except Exception:
            return agent_id

    async def _dispatch_multi_agent(
        self,
        target_agents: list[str],
        user_request: str,
        chat_history: list,
    ) -> None:
        current_history = list(chat_history) if chat_history else []
        last_agent_role = "supervisor"

        for agent_id in target_agents:
            current_role = self._resolve_agent_display_name(agent_id)
            last_agent_role = current_role

            agent_content = await self._handle_sub_agent(
                agent_id,
                user_request,
                chat_history=current_history,
                emit_done=False,
                emit_message=True,
            )
            if agent_content:
                current_history.append({
                    "role": "assistant",
                    "agent": current_role,
                    "content": agent_content
                })

        await self.send_event(SupervisorEvent(
            type=EventType.DONE, role=last_agent_role, content=""
        ))
        if self.debate_record:
            self.debate_repo.update_status(self.debate_record.id, "finished")

    async def _handle_start_request(self, raw_start: dict) -> None:
        user_request = raw_start.get("user_request", "")
        if not user_request:
            await self.websocket.send_json({"type": "error", "content": "user_request is required"})
            return

        try:
            _ = get_llm_provider(self.settings.default_provider)
        except Exception as e:
            await self.websocket.send_json({"type": "error", "content": f"Default provider error: {str(e)}"})
            return

        target_agents = self._extract_target_agents(raw_start)
        primary_target = target_agents[0] if target_agents else "supervisor"
        attachments = raw_start.get("attachments", [])
        chat_history = raw_start.get("history", [])
        user_id = self.authenticated_user.id if self.authenticated_user else raw_start.get("user_id")
        target_domain = raw_start.get("target_domain")

        self._init_session_and_trace(
            raw_start.get("session_id"),
            user_request,
            primary_target,
            user_id=user_id,
            attachments=attachments,
        )

        if len(target_agents) > 1:
            await self._dispatch_multi_agent(target_agents, user_request, chat_history)
        else:
            await self._dispatch_target(
                primary_target,
                user_request,
                chat_history,
                attachments,
                target_domain=target_domain,
            )

    async def process_messages(self) -> None:
        from src.presentation.api.dependencies.auth import authenticate_websocket

        while True:
            raw_start = await self.websocket.receive_json()
            if self.auth_service is not None:
                refreshed_user = await authenticate_websocket(
                    self.websocket, self.auth_service, self.settings
                )
                if not refreshed_user:
                    return
                self.authenticated_user = refreshed_user
            msg_type = raw_start.get("type")
            if msg_type in ("cancel", "abort"):
                self.abort()
                await self.websocket.send_json({
                    "type": "done",
                    "role": "supervisor",
                    "content": "Debate cancelado por el usuario."
                })
                continue
            if msg_type != "start":
                await self.websocket.send_json({"type": "error", "content": "Expected 'start' message"})
                continue
            await self._handle_start_request(raw_start)

    def abort(self) -> None:
        if self.debate_record:
            try:
                record = self.debate_repo.find_by_id(self.debate_record.id, allow_unscoped=True)
                if record and record.status == "running":
                    self.debate_repo.update_status(self.debate_record.id, "aborted")
            except Exception:
                pass

        if self.current_trace:
            try:
                self.observability.end_trace(
                    trace_context=self.current_trace,
                    status="ABORTED",
                    output="Debate execution was aborted"
                )
            except Exception:
                pass
            self.current_trace = None


@router.websocket("/ws/debate")
async def debate_ws(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for debate streaming.
    
    Flow:
    1. CSWSH check (Origin).
    2. Authenticate strictly (Fail-Closed).
    3. Accept connection.
    4. Wait for 'start' message with parameters.
    5. Run SupervisorAgent.run() async generator or target sub-agent.
    6. Send each event as JSON.
    7. On HITL_REQUIRED, wait for 'hitl_response' from client before continuing.
    """
    from src.presentation.api.dependencies.auth import (
        get_auth_service,
        validate_websocket_origin,
        authenticate_websocket,
    )
    settings = get_settings()

    # 1. CSWSH protection: Validate Origin header if present
    if not validate_websocket_origin(websocket, settings):
        await websocket.close(code=1008, reason="Origin not allowed")
        return

    # 2. Fall-closed resolution of AuthService
    try:
        auth_service = get_auth_service(websocket)
    except Exception:
        logger.exception("Failed to obtain auth service in websocket handshake")
        await websocket.close(code=1011, reason="Authentication service unavailable")
        return

    # 3. Authenticate strictly (Fail-closed)
    authenticated_user = await authenticate_websocket(websocket, auth_service, settings)
    if not authenticated_user:
        return

    await websocket.accept()
    handler = DebateWebSocketHandler(
        websocket,
        authenticated_user=authenticated_user,
        auth_service=auth_service,
    )
    
    try:
        await handler.process_messages()
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
        handler.abort()
    except Exception as e:
        logger.exception("Error during debate WebSocket execution")
        if handler.current_trace:
            try:
                handler.observability.end_trace(
                    trace_context=handler.current_trace,
                    status="ERROR",
                    output=str(e)
                )
            except Exception:
                pass
            handler.current_trace = None
        handler.abort()
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
            await websocket.close(code=1011)
        except Exception:
            pass

