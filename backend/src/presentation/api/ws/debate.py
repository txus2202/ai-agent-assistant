"""
Presentation: WS Debate Route

WebSocket endpoint for streaming the multi-agent debate and handling
real-time HITL decisions (ADR-016).
"""
from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.application.agents.sub_agent_runner import SubAgentRunner
from src.application.agents.supervisor_agent import SupervisorAgent
from src.application.services.learn_from_source import LearnFromSource, SourceType
from src.domain.agents.agent_role import AgentRole
from src.domain.agents.supervisor_events import HITLResponse, SupervisorEvent, EventType
from src.domain.value_objects.debate_record import DebateRecord
from src.infrastructure.llm.registry import get_llm_provider
from src.infrastructure.persistence.sqlite_agent_config_repository import SqliteAgentConfigRepository
from src.infrastructure.persistence.sqlite_debate_repository import SqliteDebateRepository
from src.infrastructure.rag.chroma_document_store import ChromaDBDocumentStore
from src.presentation.api.config import get_settings
from src.presentation.api.ws.serializers import dict_to_hitl_response, event_to_dict

router = APIRouter(tags=["debate"])
logger = logging.getLogger(__name__)


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

    async def send_event(self, event: SupervisorEvent) -> None:
        """Helper to send event to WS and append to SQLite."""
        event_dict = event_to_dict(event)
        await self.websocket.send_json(event_dict)
        if self.debate_record:
            self.debate_repo.append_event(self.debate_record.id, json.dumps(event_dict))
            if event.type == EventType.DONE:
                self.debate_repo.update_status(self.debate_record.id, "completed")

    async def hitl_callback(self, event: SupervisorEvent) -> HITLResponse:
        """
        Pause debate execution and await client response for the HITL checkpoint.
        (The HITL_REQUIRED event itself was already yielded by the generator and sent).
        """
        raw_resp = await self.websocket.receive_json()
        return dict_to_hitl_response(raw_resp)

    async def _handle_supervisor(self, user_request: str) -> None:
        async for event in SupervisorAgent.run(
            user_request=user_request,
            document_store=self.document_store,
            agent_config_repo=self.agent_config_repo,
            llm_factory=get_llm_provider,
            hitl_callback=self.hitl_callback,
        ):
            await self.send_event(event)

    async def _handle_learning(self, attachments: list[str]) -> None:
        yield_event = SupervisorEvent(type=EventType.AGENT_STARTED, role=AgentRole.LEARNING, content="")
        await self.send_event(yield_event)
        
        config = self.agent_config_repo.find_by_role(AgentRole.LEARNING.value)
        prov_name = config.provider if config else self.settings.default_provider
        mod_name = config.model_name if config else self.settings.default_model
        llm_prov = get_llm_provider(prov_name)
        
        results = []
        for attachment_path in attachments:
            res = await asyncio.to_thread(
                LearnFromSource.run,
                source=attachment_path,
                source_type=SourceType.PDF,
                llm_provider=llm_prov,
                document_store=self.document_store,
                vault_root=Path(self.settings.obsidian_vault_path),
                model_name=mod_name
            )
            if res.errors:
                results.append(f"❌ Error processing {attachment_path}: {res.errors}")
            else:
                results.append(f"✅ Successfully learned from {attachment_path}. Generated {res.generated_file.name}")
                
        content = "\n".join(results) or "No attachments provided to learn from."
        await self.send_event(SupervisorEvent(
            type=EventType.AGENT_COMPLETED, role=AgentRole.LEARNING, content=content
        ))
        await self.send_event(SupervisorEvent(
            type=EventType.DONE, role=None, content=content
        ))

    async def _handle_sub_agent(self, target_agent: str, user_request: str) -> None:
        try:
            role_enum = AgentRole(target_agent)
            await self.send_event(SupervisorEvent(
                type=EventType.AGENT_STARTED, role=role_enum, content=""
            ))
            
            config = self.agent_config_repo.find_by_role(role_enum.value)
            prov_name = config.provider if config else self.settings.default_provider
            mod_name = config.model_name if config else self.settings.default_model
            llm_prov = get_llm_provider(prov_name)
            
            resp = await SubAgentRunner.run(
                role=role_enum,
                user_request=user_request,
                llm_provider=llm_prov,
                document_store=self.document_store,
                model_name=mod_name
            )
            
            await self.send_event(SupervisorEvent(
                type=EventType.AGENT_COMPLETED, role=role_enum, content=resp.content
            ))
            await self.send_event(SupervisorEvent(
                type=EventType.DONE, role=None, content=resp.content
            ))
            
        except ValueError:
            if self.debate_record:
                self.debate_repo.update_status(self.debate_record.id, "aborted")
            await self.websocket.send_json({"type": "error", "content": f"Unknown agent role: {target_agent}"})
            await self.websocket.close(code=1003)

    async def process_messages(self) -> None:
        raw_start = await self.websocket.receive_json()
        if raw_start.get("type") != "start":
            await self.websocket.send_json({"type": "error", "content": "Expected 'start' message"})
            await self.websocket.close(code=1003)
            return

        user_request = raw_start.get("user_request", "")
        target_agent = raw_start.get("target_agent", "supervisor")
        attachments = raw_start.get("attachments", [])

        if not user_request:
            await self.websocket.send_json({"type": "error", "content": "user_request is required"})
            await self.websocket.close(code=1003)
            return

        try:
            _ = get_llm_provider(self.settings.default_provider)
        except Exception as e:
            await self.websocket.send_json({"type": "error", "content": f"Default provider error: {str(e)}"})
            await self.websocket.close(code=1011)
            return

        self.debate_record = DebateRecord(
            user_request=user_request,
            target_agent=target_agent,
            status="running"
        )
        self.debate_repo.create(self.debate_record)

        if target_agent == "supervisor":
            await self._handle_supervisor(user_request)
        elif target_agent == AgentRole.LEARNING.value:
            await self._handle_learning(attachments)
        else:
            await self._handle_sub_agent(target_agent, user_request)

    def abort(self) -> None:
        if self.debate_record:
            try:
                record = self.debate_repo.find_by_id(self.debate_record.id)
                if record and record.status == "running":
                    self.debate_repo.update_status(self.debate_record.id, "aborted")
            except Exception:
                pass


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
        handler.abort()
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
            await websocket.close(code=1011)
        except Exception:
            pass
