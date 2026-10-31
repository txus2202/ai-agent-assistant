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
from typing import Any

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
    r"^(?:aprende\s+esto|aprende|memoriza|guarda\s+este\s+conocimiento)[:\s]+(.+)",
    re.IGNORECASE | re.DOTALL,
)


def _detect_source_type(source: str) -> SourceType:
    lower = source.lower()
    if lower.startswith("http://") or lower.startswith("https://"):
        return SourceType.URL
    if lower.endswith(".pdf"):
        return SourceType.PDF
    if lower.endswith((".md", ".markdown")):
        return SourceType.MARKDOWN
    if lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
        return SourceType.IMAGE
    return SourceType.PDF


def _extract_tags(text: str) -> list[str]:
    tags: list[str] = []
    # 1. Bracket syntax: [tags: foo, bar] or [tag: foo]
    bracket_match = re.search(r"\[(?:tags?|etiquetas?):\s*([^\]]+)\]", text, re.IGNORECASE)
    if bracket_match:
        for t in bracket_match.group(1).split(","):
            clean = t.strip().lstrip("#")
            if clean and clean not in tags:
                tags.append(clean)

    # 2. Natural language syntax: (con tags|con etiquetas|tags:|etiquetas:) a, b
    nl_match = re.search(
        r"(?:con (?:los )?(?:tags|etiquetas)|(?:^|\s)(?:tags|etiquetas)):\s*([^#\n\[\]]+)",
        text,
        re.IGNORECASE,
    )
    if nl_match:
        for t in nl_match.group(1).split(","):
            clean = t.strip().lstrip("#")
            if clean and clean not in tags and not clean.startswith(("http://", "https://")):
                tags.append(clean)

    # 3. Hashtags: #atenea #seguridad
    hashtags = re.findall(r"(?<!\S)#([a-zA-Z0-9_\-\.]+)", text)
    for h in hashtags:
        clean = h.strip()
        if clean and clean not in tags:
            tags.append(clean)

    return tags


def _is_skip_tags_response(text: str) -> bool:
    low = text.strip().lower()
    return low in (
        "sin tags", "sin tag", "sin etiquetas", "sin etiqueta",
        "no", "ninguno", "ninguna", "asímilalo directamente", "asimilalo directamente",
        "directamente", "adelante", "omitir", "ningun tag", "ninguna etiqueta", "no gracias"
    ) or low.startswith(("sin tag", "sin etiqueta", "asimil", "adelante"))


class DebateWebSocketHandler:
    """Handles the WebSocket debate streaming and HITL responses."""
    
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.settings = get_settings()
        db_path = str(self.settings.sqlite_db_path)
        self.agent_config_repo = SqliteAgentConfigRepository(db_path)
        self.debate_repo = SqliteDebateRepository(db_path)
        self.document_store = ChromaDBDocumentStore(
            persist_directory=str(self.settings.chroma_persist_dir)
        )
        self.debate_record: DebateRecord | None = None
        self.observability = get_observability_service()
        self.current_trace: TraceContext | None = None
        self.active_spans: dict[str, SpanContext] = {}

    def _persist_event(self, event_dict: dict[str, Any], event: SupervisorEvent) -> None:
        if not self.debate_record:
            return
        self.debate_repo.append_event(self.debate_record.id, json.dumps(event_dict))
        if event.type == EventType.DONE:
            self.debate_repo.update_status(self.debate_record.id, "completed")

    def _on_agent_started(self, event: SupervisorEvent) -> None:
        if not (self.current_trace and event.role):
            return
        role_val = event.role.value if hasattr(event.role, "value") else str(event.role)
        config = self.agent_config_repo.find_by_role(role_val)
        model_name = config.model_name if config else self.settings.default_model
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
            if ev.get("type") in ("agent_completed", "done"):
                meta = ev.get("metadata", {})
                if isinstance(meta, dict) and meta.get("pending_learning"):
                    raw = meta.get("pending_learning")
                    if isinstance(raw, str):
                        try:
                            return json.loads(raw)
                        except Exception:
                            return None
                    if isinstance(raw, dict):
                        return raw
            if ev.get("type") == "user_message":
                continue
            break
        return None

    async def _execute_learning_ingest(
        self,
        text_to_learn: str,
        attachments: list[str],
        tags: list[str],
        llm_prov: Any,
        mod_name: str,
    ) -> list[str]:
        results: list[str] = []
        tag_suffix = f" [tags: {', '.join(tags)}]" if tags else ""
        if attachments:
            for attachment_path in attachments:
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
                )
                if res.errors:
                    results.append(f"❌ Error al procesar {attachment_path}: {res.errors}")
                else:
                    file_name = res.generated_file.name if res.generated_file else "nota"
                    results.append(f"✅ Conocimiento asimilado desde {attachment_path}. Generada nota: {file_name}{tag_suffix}")
        elif text_to_learn:
            res = await asyncio.to_thread(
                LearnFromSource.run,
                source=text_to_learn,
                source_type=SourceType.TEXT,
                llm_provider=llm_prov,
                document_store=self.document_store,
                vault_root=self.settings.vault_root,
                model_name=mod_name,
                tags=tags,
            )
            if res.errors:
                results.append(f"❌ Error al aprender el texto: {res.errors}")
            else:
                file_name = res.generated_file.name if res.generated_file else "nota"
                results.append(f"✅ He asimilado y guardado este conocimiento en mi memoria persistente y en el Vault ({file_name}){tag_suffix}.")
        return results

    async def _handle_learning(
        self,
        learn_profile: Any,
        user_request: str,
        attachments: list[str],
        directive_match: re.Match[str] | None = None,
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
        text_to_learn = directive_match.group(1).strip() if directive_match else ""

        # If user did NOT specify tags via hashtags or syntax, prompt them first
        if not extracted_tags:
            ask_content = (
                "He recibido este conocimiento para asimilarlo. "
                "Antes de sellarlo e integrarlo en el Vault, ¿deseas catalogarlo con algún tag o etiqueta específico "
                "(por ejemplo: `#atenea`, `#arquitectura`, `#seguridad`), o prefieres que lo asimile directamente según su contenido?"
            )
            learn_meta = {
                "model": mod_name,
                "pending_learning": json.dumps({
                    "text": text_to_learn,
                    "attachments": attachments,
                }),
            }
            await self.send_event(SupervisorEvent(
                type=EventType.AGENT_COMPLETED, role=learn_role, content=ask_content, metadata=learn_meta
            ))
            await self.send_event(SupervisorEvent(
                type=EventType.DONE, role=learn_role, content=ask_content, metadata=learn_meta
            ))
            return

        results = await self._execute_learning_ingest(
            text_to_learn=text_to_learn,
            attachments=attachments,
            tags=extracted_tags,
            llm_prov=llm_prov,
            mod_name=mod_name,
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
        
        tags: list[str] = []
        if not _is_skip_tags_response(user_request):
            tags = _extract_tags(user_request)
            if not tags:
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
        )
        content = "\n".join(results) or "No se proporcionó contenido para el aprendizaje."
        learn_meta = {"model": mod_name}
        await self.send_event(SupervisorEvent(
            type=EventType.AGENT_COMPLETED, role=learn_role, content=content, metadata=learn_meta
        ))
        await self.send_event(SupervisorEvent(
            type=EventType.DONE, role=learn_role, content=content, metadata=learn_meta
        ))

    async def _handle_sub_agent(self, target_agent: str, user_request: str, chat_history: list[dict[str, Any]] | None = None) -> None:
        try:
            profile = get_profile(target_agent)
            agent_role = profile.display_name
            await self.send_event(SupervisorEvent(
                type=EventType.AGENT_STARTED, role=agent_role, content=""
            ))
            
            config = self.agent_config_repo.find_by_role(profile.id)
            if not config:
                config = self.agent_config_repo.find_by_role(agent_role)
            prov_name = config.provider if config else self.settings.default_provider
            mod_name = config.model_name if config else self.settings.default_model
            llm_prov = get_llm_provider(prov_name)
            
            runner_kwargs = {"chat_history": chat_history} if chat_history else {}
            resp = await SubAgentRunner.run(
                role=agent_role,
                user_request=user_request,
                llm_provider=llm_prov,
                document_store=self.document_store,
                model_name=mod_name,
                **runner_kwargs,
            )
            
            sub_meta = {
                "model": resp.model_name or mod_name,
                "prompt_tokens": str(resp.tokens.get("input", 0)),
                "completion_tokens": str(resp.tokens.get("output", 0)),
                "total_tokens": str(resp.tokens.get("total", 0)),
                "latency_seconds": str(resp.latency),
                "tokens": str(resp.tokens.get("total", 0)),
            }
            await self.send_event(SupervisorEvent(
                type=EventType.AGENT_COMPLETED, role=agent_role, content=resp.content, metadata=sub_meta
            ))
            await self.send_event(SupervisorEvent(
                type=EventType.DONE, role=agent_role, content=resp.content, metadata=sub_meta
            ))
            
        except KeyError:
            if self.debate_record:
                self.debate_repo.update_status(self.debate_record.id, "aborted")
            await self.websocket.send_json({"type": "error", "content": f"Unknown agent role: {target_agent}"})
            await self.websocket.close(code=1003)

    def _init_session_and_trace(self, session_id: str | None, user_request: str, target_agent: str) -> None:
        existing_record = self.debate_repo.find_by_id(session_id) if session_id else None

        if existing_record:
            self.debate_record = existing_record
            self.debate_record.target_agent = target_agent
            self.debate_repo.update_session(self.debate_record.id, status="running", target_agent=target_agent)
        else:
            self.debate_record = DebateRecord(
                id=session_id or str(uuid.uuid4()),
                user_request=user_request,
                target_agent=target_agent,
                status="running"
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

        self.current_trace = self.observability.start_trace(
            name=f"debate_{target_agent}",
            session_id=self.debate_record.id,
            metadata={
                "user_request": user_request,
                "target_agent": target_agent,
            }
        )

    async def _dispatch_target(self, target_agent: str, user_request: str, chat_history: list, attachments: list) -> bool:
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
            directive_match = LEARN_DIRECTIVE_REGEX.match(user_request.strip()) if user_request else None
            pending_learning = self._get_pending_learning() if not directive_match else None
            if pending_learning:
                await self._handle_pending_learning(target_profile, user_request, pending_learning)
            elif attachments or directive_match:
                await self._handle_learning(target_profile, user_request, attachments, directive_match)
            else:
                await self._handle_sub_agent(target_agent, user_request, chat_history=chat_history)
        else:
            await self._handle_sub_agent(target_agent, user_request, chat_history=chat_history)
        return True

    async def _handle_start_request(self, raw_start: dict) -> None:
        user_request = raw_start.get("user_request", "")
        target_agent = raw_start.get("target_agent", "supervisor")
        attachments = raw_start.get("attachments", [])
        chat_history = raw_start.get("history", [])

        if not user_request:
            await self.websocket.send_json({"type": "error", "content": "user_request is required"})
            return

        try:
            _ = get_llm_provider(self.settings.default_provider)
        except Exception as e:
            await self.websocket.send_json({"type": "error", "content": f"Default provider error: {str(e)}"})
            return

        self._init_session_and_trace(raw_start.get("session_id"), user_request, target_agent)
        await self._dispatch_target(target_agent, user_request, chat_history, attachments)

    async def process_messages(self) -> None:
        while True:
            raw_start = await self.websocket.receive_json()
            if raw_start.get("type") != "start":
                await self.websocket.send_json({"type": "error", "content": "Expected 'start' message"})
                continue
            await self._handle_start_request(raw_start)

    def abort(self) -> None:
        if self.debate_record:
            try:
                record = self.debate_repo.find_by_id(self.debate_record.id)
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
    1. Accept connection.
    2. Wait for 'start' message with parameters.
    3. Run SupervisorAgent.run() async generator or target sub-agent.
    4. Send each event as JSON.
    5. On HITL_REQUIRED, wait for 'hitl_response' from client before continuing.
    """
    await websocket.accept()
    handler = DebateWebSocketHandler(websocket)
    
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

