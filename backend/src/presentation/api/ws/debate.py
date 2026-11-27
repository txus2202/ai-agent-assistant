"""
Presentation: WebSocket /ws/debate Endpoint

Thin transport coordinator managing WebSocket message framing, session IDOR
guards, cancellation, and delegation to SupervisorAgent, SubAgentRunner,
DebateLearningCoordinator, and DebateObservabilityTracker.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.application.agents.sub_agent_runner import SubAgentRunner
from src.application.agents.supervisor_agent import DebateRunOptions, SupervisorAgent
from src.application.services.learn_from_source import SourceType
from src.application.services.llm_provider_registry import LLMProviderRegistry
from src.application.services.user_topology_service import ResolvedUserTopology, UserTopologyService
from src.domain.agents.sub_agent_profiles import SubAgentProfile
from src.domain.agents.supervisor_events import EventType, HITLDecision, HITLResponse, SupervisorEvent
from src.domain.ports.agent_catalog_repository import IAgentCatalogRepository, ITopologyProvider
from src.domain.ports.document_parser import IDocumentParser
from src.domain.ports.document_store import IDocumentStore
from src.domain.ports.image_generator import IImageGenerator
from src.domain.ports.llm_provider import ILLMProvider
from src.domain.ports.observability_service import IObservabilityService, SpanContext, TraceContext
from src.domain.ports.source_extractor import ISourceExtractor
from src.domain.value_objects.debate_record import DebateRecord
from src.infrastructure.persistence.sqlite_agent_config_repository import (
    SqliteAgentConfigRepository,
    UserScopedAgentConfigRepository,
)
from src.infrastructure.persistence.sqlite_debate_repository import SqliteDebateRepository
from src.infrastructure.persistence.sqlite_user_topology_repository import SqliteUserTopologyRepository
from src.presentation.api.config import get_settings
from src.presentation.api.dependencies.agents import (
    get_agent_catalog,
    get_topology_provider,
    resolve_fallback_review_rounds,
)
from src.presentation.api.dependencies.learning import get_source_extractors
from src.presentation.api.dependencies.llm import get_image_generator, get_llm_registry
from src.presentation.api.dependencies.rag import get_document_parser, get_document_store
from src.presentation.api.routes.observability import get_observability_service
from src.presentation.api.routes.upload import resolve_user_attachment_path
from src.presentation.api.ws.debate_learning import DebateLearningCoordinator
from src.presentation.api.ws.debate_observability_tracker import DebateObservabilityTracker
from src.presentation.api.ws.learning_command_parser import validate_attachments
from src.presentation.api.ws.serializers import dict_to_hitl_response, event_to_dict

router = APIRouter(tags=["debate"])
logger = logging.getLogger(__name__)


class DebateCancelledError(Exception):
    """Raised when the client explicitly cancels/aborts an active debate."""


def _reset_wake_word_sync() -> None:
    try:
        from src.presentation.api.ws.wake_word import wake_word_service
        wake_word_service.reset()
    except Exception:
        logger.debug("Wake-word service reset skipped or unavailable", exc_info=True)


class DebateWebSocketHandler:
    """Handles WebSocket debate streaming, HITL callbacks, and delegation."""

    def __init__(
        self,
        websocket: WebSocket,
        authenticated_user: Any = None,
        auth_service: Any = None,
        document_store: IDocumentStore | None = None,
        agent_catalog: IAgentCatalogRepository | None = None,
        topology_provider: ITopologyProvider | None = None,
        image_generator: IImageGenerator | None = None,
        document_parser: IDocumentParser | None = None,
        source_extractors: dict[SourceType, ISourceExtractor] | None = None,
        llm_registry: LLMProviderRegistry | None = None,
        observability: IObservabilityService | None = None,
    ) -> None:
        self.websocket = websocket
        self.authenticated_user = authenticated_user
        self.auth_service = auth_service
        app_state = getattr(getattr(websocket, "app", None), "state", None)
        self.settings = getattr(app_state, "settings", None) or get_settings()
        self._cancel_event = asyncio.Event()
        self.agent_catalog = agent_catalog or get_agent_catalog(websocket, self.settings)
        self.topology_provider = topology_provider or get_topology_provider(websocket, self.settings)
        self.image_generator = image_generator or get_image_generator(websocket, self.settings)
        self.document_parser = document_parser or get_document_parser(websocket)
        self.source_extractors = (
            source_extractors if source_extractors is not None else get_source_extractors(websocket)
        )
        self.llm_registry = llm_registry or get_llm_registry(websocket, self.settings)

        db_path = str(self.settings.sqlite_db_path)
        base_agent_repo = SqliteAgentConfigRepository(db_path, agent_catalog=self.agent_catalog)
        user_id_scope = self.authenticated_user.id if self.authenticated_user else None
        self.agent_config_repo = UserScopedAgentConfigRepository(base_agent_repo, user_id=user_id_scope)
        self.user_topology_repo = SqliteUserTopologyRepository(db_path)
        self.user_topology_service = UserTopologyService(
            agent_catalog=self.agent_catalog,
            topology_provider=self.topology_provider,
            user_topology_repo=self.user_topology_repo,
        )
        self.debate_repo = SqliteDebateRepository(db_path)
        self._document_store = document_store
        self.debate_record: DebateRecord | None = None

        self.observability = observability or get_observability_service()
        self.obs_tracker = DebateObservabilityTracker(
            observability=self.observability,
            agent_catalog=self.agent_catalog,
            agent_config_repo=self.agent_config_repo,
            default_model=self.settings.default_model,
        )
        self._learning = DebateLearningCoordinator(
            send_event=self.send_event,
            get_doc_store=self._get_doc_store,
            resolve_learning_llm_sync=self._resolve_learning_llm_sync,
            vault_root=self.settings.vault_root,
            source_extractors=self.source_extractors,
            document_parser=self.document_parser,
            get_user_id=lambda: self.authenticated_user.id if self.authenticated_user else None,
            get_debate_events=lambda: self.debate_record.events if self.debate_record else None,
            fallback_sub_agent=lambda agent, req, hist: self._handle_sub_agent(
                agent, req, chat_history=hist
            ),
        )

    @property
    def current_trace(self) -> TraceContext | None:
        return self.obs_tracker.current_trace

    @current_trace.setter
    def current_trace(self, value: TraceContext | None) -> None:
        self.obs_tracker.current_trace = value

    @property
    def active_spans(self) -> dict[str, SpanContext]:
        return self.obs_tracker.active_spans

    @property
    def document_store(self) -> IDocumentStore | None:
        return self._document_store

    @document_store.setter
    def document_store(self, value: IDocumentStore | None) -> None:
        self._document_store = value

    async def _get_doc_store(self) -> IDocumentStore:
        if self._document_store is None:
            self._document_store = await get_document_store(self.websocket)
        return self._document_store

    def _update_debate_status_sync(self, status: str) -> None:
        if self.debate_record:
            self.debate_repo.update_status(self.debate_record.id, status)

    def _end_trace_sync(self, status: str, output: str) -> None:
        self.obs_tracker.end_trace(status, output)

    def _mark_error_and_end_trace_sync(self, exc_text: str) -> None:
        self._update_debate_status_sync("error")
        self._end_trace_sync("ERROR", exc_text)

    def _persist_event(self, event_dict: dict[str, Any], event: SupervisorEvent) -> None:
        if not self.debate_record or event.type == EventType.STREAM_CHUNK:
            return
        self.debate_repo.append_event(self.debate_record.id, json.dumps(event_dict))
        if event.type == EventType.DONE:
            self.debate_repo.update_status(self.debate_record.id, "completed")

    def _record_event_sync(self, event_dict: dict[str, Any], event: SupervisorEvent) -> None:
        self._persist_event(event_dict, event)
        input_prompt = self.debate_record.user_request if self.debate_record else ""
        self.obs_tracker.track_event(event, input_prompt=input_prompt)

    async def send_event(self, event: SupervisorEvent) -> None:
        """Send serialized event over WS, persist non-chunk events, and update observability spans."""
        event_dict = event_to_dict(event)
        if self.obs_tracker.current_trace:
            if "metadata" not in event_dict or not isinstance(event_dict["metadata"], dict):
                event_dict["metadata"] = {}
            event_dict["metadata"]["trace_id"] = self.obs_tracker.current_trace.trace_id
        await self.websocket.send_json(event_dict)
        if event.type != EventType.STREAM_CHUNK:
            await asyncio.to_thread(self._record_event_sync, event_dict, event)

    def _finalize_hitl_response_sync(self, hitl_resp: HITLResponse) -> None:
        self.obs_tracker.score_hitl_decision(hitl_resp)
        if hitl_resp.decision == HITLDecision.REFINE and hitl_resp.feedback and self.debate_record:
            refine_event_dict = {
                "type": "user_message",
                "role": "user",
                "content": hitl_resp.feedback,
                "metadata": {"decision": "refine", "target_agents": hitl_resp.target_agents},
            }
            self.debate_repo.append_event(self.debate_record.id, json.dumps(refine_event_dict))
        _reset_wake_word_sync()

    async def hitl_callback(self, event: SupervisorEvent) -> HITLResponse:
        """Pause debate execution and await client response for the HITL checkpoint."""
        if self._cancel_event.is_set():
            raise DebateCancelledError("Debate cancelled before HITL checkpoint response")

        raw_resp = await self.websocket.receive_json()
        if isinstance(raw_resp, dict) and (
            str(raw_resp.get("type", "")).lower() in ("cancel", "abort")
            or str(raw_resp.get("decision", "")).lower() in ("cancel", "abort")
        ):
            await self.abort_async()
            raise DebateCancelledError("Debate cancelled by user during HITL checkpoint")

        hitl_resp = dict_to_hitl_response(raw_resp)
        await asyncio.to_thread(self._finalize_hitl_response_sync, hitl_resp)
        return hitl_resp

    def _resolve_effective_topology_sync(self) -> ResolvedUserTopology:
        user_id = self.authenticated_user.id if self.authenticated_user else None
        return self.user_topology_service.resolve_for_user(
            user_id,
            fallback_review_rounds=resolve_fallback_review_rounds(self.settings),
        )

    async def _handle_supervisor(
        self,
        user_request: str,
        chat_history: list[dict[str, Any]] | None = None,
    ) -> None:
        try:
            doc_store = await self._get_doc_store()
            resolved_topo = await asyncio.to_thread(self._resolve_effective_topology_sync)
            async for event in SupervisorAgent.run(
                user_request=user_request,
                document_store=doc_store,
                agent_config_repo=self.agent_config_repo,
                llm_factory=self.llm_registry.get,
                hitl_callback=self.hitl_callback,
                chat_history=chat_history,
                review_rounds=resolved_topo.review_rounds,
                topology=resolved_topo.topology,
                cancel_event=self._cancel_event,
                agent_catalog=self.agent_catalog,
                topology_provider=self.topology_provider,
                options=DebateRunOptions(
                    default_provider=self.settings.default_provider,
                    default_model=self.settings.default_model,
                    image_generator=self.image_generator,
                ),
            ):
                if self._cancel_event.is_set():
                    raise DebateCancelledError("Debate cancelled by user")
                await self.send_event(event)
        except DebateCancelledError:
            logger.info("Debate cancelled cleanly during execution")
            await self.abort_async()
            try:
                await self.websocket.send_json({
                    "type": "done",
                    "role": "supervisor",
                    "content": "Debate cancelado por el usuario.",
                    "metadata": {"cancelled": "true", "metrics_reported": "true"},
                })
            except Exception:
                logger.debug("Failed to send cancel confirmation over closing websocket", exc_info=True)
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected during supervisor debate; aborting")
            await self.abort_async()
            raise
        except Exception as exc:
            logger.exception("Error during supervisor debate execution")
            await asyncio.to_thread(self._mark_error_and_end_trace_sync, str(exc))
            await self.send_event(SupervisorEvent(
                type=EventType.ERROR, role="supervisor", content=str(exc)
            ))
        finally:
            await asyncio.to_thread(_reset_wake_word_sync)

    def _resolve_learning_llm_sync(self, learn_profile: Any) -> tuple[ILLMProvider, str]:
        learn_role = learn_profile.display_name
        config = self.agent_config_repo.find_by_role(learn_profile.id)
        if not config:
            config = self.agent_config_repo.find_by_role(learn_role)
        prov_name = config.provider if config else self.settings.default_provider
        mod_name = config.model_name if config else self.settings.default_model
        return self.llm_registry.get(prov_name), mod_name

    def _resolve_agent_llm(self, profile: SubAgentProfile, agent_role: str) -> tuple[ILLMProvider, str]:
        config = self.agent_config_repo.find_by_role(profile.id) or self.agent_config_repo.find_by_role(agent_role)
        default_prov = getattr(profile, "default_provider", "") or self.settings.default_provider
        default_mod = getattr(profile, "default_model", "") or self.settings.default_model
        prov_name = config.provider if (config and config.provider) else default_prov
        mod_name = config.model_name if (config and config.model_name) else default_mod
        return self.llm_registry.get(prov_name), mod_name

    def _resolve_sub_agent_runtime_sync(
        self,
        profile: SubAgentProfile,
        agent_role: str,
    ) -> tuple[ILLMProvider, str, dict[str, Any]]:
        llm_prov, mod_name = self._resolve_agent_llm(profile, agent_role)
        config = self.agent_config_repo.find_by_role(profile.id) or self.agent_config_repo.find_by_role(agent_role)
        extra_kwargs: dict[str, Any] = {}
        if config and getattr(config, "rag_top_k", None) is not None:
            extra_kwargs["rag_top_k"] = config.rag_top_k
        if config and getattr(config, "rag_min_score", None) is not None:
            extra_kwargs["rag_min_score"] = config.rag_min_score
        return llm_prov, mod_name, extra_kwargs

    async def _emit_sub_agent_completion(
        self,
        agent_role: str,
        resp: Any,
        mod_name: str,
        emit_message: bool,
        emit_done: bool,
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
                type=EventType.DONE,
                role=agent_role,
                content=resp.content,
                metadata={"model": sub_meta["model"], "metrics_reported": "true"},
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
            profile = self.agent_catalog.get_profile(target_agent)
            agent_role = profile.display_name
            await self.send_event(SupervisorEvent(
                type=EventType.AGENT_STARTED, role=agent_role, content=""
            ))

            doc_store = await self._get_doc_store()
            llm_prov, mod_name, rag_kwargs = await asyncio.to_thread(
                self._resolve_sub_agent_runtime_sync, profile, agent_role
            )
            runner_kwargs: dict[str, Any] = {"chat_history": chat_history} if chat_history else {}
            runner_kwargs.update(rag_kwargs)
            resp = await SubAgentRunner.run(
                role=agent_role,
                user_request=user_request,
                llm_provider=llm_prov,
                document_store=doc_store,
                model_name=mod_name,
                agent_catalog=self.agent_catalog,
                image_generator=self.image_generator,
                **runner_kwargs,
            )
            await self._emit_sub_agent_completion(agent_role, resp, mod_name, emit_message, emit_done)
            return resp.content

        except KeyError:
            await asyncio.to_thread(self._update_debate_status_sync, "aborted")
            await self.websocket.send_json({"type": "error", "content": f"Unknown agent role: {target_agent}"})
            await self.websocket.close(code=1003)
            return None
        except Exception as exc:
            logger.exception("Error during sub-agent execution: %s", agent_role)
            await asyncio.to_thread(self._mark_error_and_end_trace_sync, str(exc))
            await self.send_event(SupervisorEvent(type=EventType.ERROR, role=agent_role, content=str(exc)))
            return None

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

        user_event_dict = {
            "type": "user_message",
            "role": "user",
            "content": user_request,
            "metadata": {"target_agent": target_agent},
        }
        self.debate_repo.append_event(self.debate_record.id, json.dumps(user_event_dict))

        raw_user = (
            self.authenticated_user.username if self.authenticated_user else user_id
        )
        default_user = str(
            getattr(self.settings, "langfuse_default_user_id", "local_user") or "local_user"
        )
        effective_user: str = str(raw_user) if raw_user else default_user

        self.obs_tracker.start_trace(
            session_id=self.debate_record.id,
            user_request=user_request,
            target_agent=target_agent,
            user_id=effective_user,
            attachments=attachments,
        )

    async def _dispatch_target(
        self,
        target_agent: str,
        user_request: str,
        chat_history: list[Any],
        attachments: list[str],
        target_domain: str | None = None,
    ) -> bool:
        try:
            target_profile = self.agent_catalog.get_profile(target_agent)
        except KeyError:
            await asyncio.to_thread(self._update_debate_status_sync, "aborted")
            await self.websocket.send_json({"type": "error", "content": f"Unknown agent role: {target_agent}"})
            await self.websocket.close(code=1003)
            return False

        if target_profile.is_supervisor:
            await self._handle_supervisor(user_request, chat_history=chat_history)
        elif target_profile.can_ingest_documents:
            await self._learning.dispatch(
                target_profile, target_agent, user_request, chat_history, attachments, target_domain=target_domain
            )
        else:
            await self._handle_sub_agent(target_agent, user_request, chat_history=chat_history)
        return True

    @staticmethod
    def _extract_target_agents(raw_start: dict[str, Any]) -> list[str]:
        target_agents = raw_start.get("target_agents", [])
        if target_agents:
            return list(target_agents)
        target_agent = raw_start.get("target_agent", "supervisor")
        return [target_agent] if isinstance(target_agent, str) else list(target_agent)

    def _resolve_agent_display_name(self, agent_id: str) -> str:
        try:
            return self.agent_catalog.get_profile(agent_id).display_name
        except KeyError:
            logger.debug("Agent '%s' not found in catalog; using raw identifier", agent_id)
            return agent_id

    async def _dispatch_multi_agent(
        self,
        target_agents: list[str],
        user_request: str,
        chat_history: list[Any],
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
                    "content": agent_content,
                })

        await self.send_event(SupervisorEvent(
            type=EventType.DONE, role=last_agent_role, content=""
        ))
        await asyncio.to_thread(self._update_debate_status_sync, "finished")

    async def _handle_start_request(self, raw_start: dict[str, Any]) -> None:
        self._cancel_event.clear()
        user_request = raw_start.get("user_request", "")
        if not user_request:
            await self.websocket.send_json({"type": "error", "content": "user_request is required"})
            return

        try:
            _ = self.llm_registry.get(self.settings.default_provider)
        except Exception as exc:
            await self.websocket.send_json({"type": "error", "content": f"Default provider error: {str(exc)}"})
            return

        target_agents = self._extract_target_agents(raw_start)
        primary_target = target_agents[0] if target_agents else "supervisor"
        user_id_scope = self.authenticated_user.id if self.authenticated_user else None
        try:
            attachments = await asyncio.to_thread(
                validate_attachments,
                raw_start.get("attachments", []),
                user_id_scope,
                resolve_user_attachment_path,
            )
        except (ValueError, PermissionError) as exc:
            logger.warning("Rejected unsafe attachments in debate start request: %s", exc)
            await self.websocket.send_json({"type": "error", "content": "Invalid or unauthorized attachment path"})
            return

        chat_history = raw_start.get("history", [])
        user_id = self.authenticated_user.id if self.authenticated_user else raw_start.get("user_id")
        target_domain = raw_start.get("target_domain")

        await asyncio.to_thread(
            self._init_session_and_trace,
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
                await self.abort_async()
                await self.websocket.send_json({
                    "type": "done",
                    "role": "supervisor",
                    "content": "Debate cancelado por el usuario.",
                })
                continue
            if msg_type != "start":
                await self.websocket.send_json({"type": "error", "content": "Expected 'start' message"})
                continue
            await self._handle_start_request(raw_start)

    def _finalize_abort_sync(self) -> None:
        if self.debate_record:
            try:
                record = self.debate_repo.find_by_id(self.debate_record.id, allow_unscoped=True)
                if record and record.status == "running":
                    self.debate_repo.update_status(self.debate_record.id, "aborted")
            except Exception:
                logger.warning(
                    "Failed to update debate %s status to aborted during finalization",
                    self.debate_record.id,
                    exc_info=True,
                )
        self._end_trace_sync("ABORTED", "Debate execution was aborted")

    def abort(self) -> None:
        self._cancel_event.set()
        self._finalize_abort_sync()

    async def abort_async(self) -> None:
        self._cancel_event.set()
        await asyncio.to_thread(self._finalize_abort_sync)


@router.websocket("/ws/debate")
async def debate_ws(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for debate streaming.

    Flow:
      1. CSWSH check (Origin).
      2. Authenticate strictly (Fail-Closed).
      3. Accept connection and delegate messages to DebateWebSocketHandler.
    """
    from src.presentation.api.dependencies.auth import (
        authenticate_websocket,
        get_auth_service,
        validate_websocket_origin,
    )

    settings = get_settings()

    if not validate_websocket_origin(websocket, settings):
        await websocket.close(code=1008, reason="Origin not allowed")
        return

    try:
        auth_service = get_auth_service(websocket)
    except Exception:
        logger.exception("Failed to obtain auth service in websocket handshake")
        await websocket.close(code=1011, reason="Authentication service unavailable")
        return

    authenticated_user = await authenticate_websocket(websocket, auth_service, settings)
    if not authenticated_user:
        return

    await websocket.accept()
    metrics_service = getattr(websocket.app.state, "metrics_service", None)
    if metrics_service:
        metrics_service.inc_websocket_connection("debate")

    document_store = await get_document_store(websocket)
    handler = DebateWebSocketHandler(
        websocket,
        authenticated_user=authenticated_user,
        auth_service=auth_service,
        document_store=document_store,
    )

    try:
        try:
            await handler.process_messages()
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected")
            await handler.abort_async()
        except Exception as exc:
            logger.exception("Error during debate WebSocket execution")
            await asyncio.to_thread(handler._end_trace_sync, "ERROR", str(exc))
            await handler.abort_async()
            try:
                await websocket.send_json({"type": "error", "content": str(exc)})
                await websocket.close(code=1011)
            except Exception:
                logger.debug("Failed to send error notification or close websocket after failure", exc_info=True)
    finally:
        if metrics_service:
            metrics_service.dec_websocket_connection("debate")
