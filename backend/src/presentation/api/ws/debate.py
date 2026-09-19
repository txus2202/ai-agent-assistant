"""
Presentation: WS Debate Route

WebSocket endpoint for streaming the multi-agent debate and handling
real-time HITL decisions (ADR-016).
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.application.agents.supervisor_agent import SupervisorAgent
from src.domain.agents.supervisor_events import HITLResponse, SupervisorEvent, EventType
from src.infrastructure.llm.registry import get_llm_provider
from src.infrastructure.rag.chroma_document_store import ChromaDBDocumentStore
from src.presentation.api.config import get_settings
from src.presentation.api.ws.serializers import dict_to_hitl_response, event_to_dict

router = APIRouter(tags=["debate"])
logger = logging.getLogger(__name__)


@router.websocket("/ws/debate")
async def debate_ws(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for debate streaming.
    
    Flow:
    1. Accept connection.
    2. Wait for 'start' message with parameters.
    3. Run SupervisorAgent.run() async generator.
    4. Send each event as JSON.
    5. On HITL_REQUIRED, wait for 'hitl_response' from client before continuing.
    """
    await websocket.accept()
    
    try:
        # Wait for initialization payload
        raw_start = await websocket.receive_json()
        if raw_start.get("type") != "start":
            await websocket.send_json({"type": "error", "content": "Expected 'start' message"})
            await websocket.close(code=1003)
            return

        user_request = raw_start.get("user_request", "")
        # Defaults to supervisor if not specified
        target_agent = raw_start.get("target_agent", "supervisor")
        attachments = raw_start.get("attachments", [])

        if not user_request:
            await websocket.send_json({"type": "error", "content": "user_request is required"})
            await websocket.close(code=1003)
            return

        # Setup dependencies
        settings = get_settings()
        
        # Test if the default provider works, otherwise it will fail inside the agent
        try:
            _ = get_llm_provider(settings.default_provider)
        except Exception as e:
            await websocket.send_json({"type": "error", "content": f"Default provider error: {str(e)}"})
            await websocket.close(code=1011)
            return

        # Setup Repositories
        from src.infrastructure.persistence.sqlite_agent_config_repository import SqliteAgentConfigRepository
        from src.infrastructure.persistence.sqlite_debate_repository import SqliteDebateRepository
        from src.domain.value_objects.debate_record import DebateRecord
        import json
        
        db_path = str(settings.sqlite_db_path)
        agent_config_repo = SqliteAgentConfigRepository(db_path)
        debate_repo = SqliteDebateRepository(db_path)

        # Using ChromaDB Document Store (Phase 2)
        document_store = ChromaDBDocumentStore(
            persist_directory=str(settings.chroma_persist_dir)
        )
        
        # Create Debate Record
        debate_record = DebateRecord(
            user_request=user_request,
            target_agent=target_agent,
            status="running"
        )
        debate_repo.create(debate_record)
        
        async def send_event(event: SupervisorEvent):
            """Helper to send event to WS and append to SQLite."""
            event_dict = event_to_dict(event)
            await websocket.send_json(event_dict)
            debate_repo.append_event(debate_record.id, json.dumps(event_dict))
            if event.type == EventType.DONE:
                debate_repo.update_status(debate_record.id, "completed")

        async def hitl_callback(event: SupervisorEvent) -> HITLResponse:
            """
            Pause debate execution and await client response for the HITL checkpoint.
            (The HITL_REQUIRED event itself was already yielded by the generator and sent).
            """
            # Wait for the client's decision
            # (In a production app with timeouts, we'd wrap this in asyncio.wait_for)
            raw_resp = await websocket.receive_json()
            
            # Parse the response, defaulting to APPROVE if malformed
            return dict_to_hitl_response(raw_resp)

        # ── ROUTING LOGIC ───────────────────────────────────────────────────
        if target_agent == "supervisor":
            # Run the full debate generator
            async for event in SupervisorAgent.run(
                user_request=user_request,
                document_store=document_store,
                agent_config_repo=agent_config_repo,
                llm_factory=get_llm_provider,
                hitl_callback=hitl_callback,
            ):
                await send_event(event)
                
        elif target_agent == AgentRole.LEARNING.value:
            from src.application.services.learn_from_source import LearnFromSource, SourceType
            from pathlib import Path
            import asyncio
            
            yield_event = SupervisorEvent(type=EventType.AGENT_STARTED, role=AgentRole.LEARNING, content="")
            await send_event(yield_event)
            
            config = agent_config_repo.find_by_role(AgentRole.LEARNING.value)
            prov_name = config.provider if config else settings.default_provider
            mod_name = config.model_name if config else settings.default_model
            llm_prov = get_llm_provider(prov_name)
            
            results = []
            for attachment_path in attachments:
                # We assume attachments are paths to temporary files returned by POST /upload
                res = await asyncio.to_thread(
                    LearnFromSource.run,
                    source=attachment_path,
                    source_type=SourceType.PDF, # Simplification, in reality we'd detect based on ext
                    llm_provider=llm_prov,
                    document_store=document_store,
                    vault_root=Path(settings.obsidian_vault_path),
                    model_name=mod_name
                )
                if res.errors:
                    results.append(f"❌ Error processing {attachment_path}: {res.errors}")
                else:
                    results.append(f"✅ Successfully learned from {attachment_path}. Generated {res.generated_file.name}")
                    
            content = "\n".join(results) or "No attachments provided to learn from."
            await send_event(SupervisorEvent(
                type=EventType.AGENT_COMPLETED, role=AgentRole.LEARNING, content=content
            ))
            await send_event(SupervisorEvent(
                type=EventType.DONE, role=None, content=content
            ))
            
        else:
            # Direct invocation of a single sub-agent
            from src.application.agents.sub_agent_runner import SubAgentRunner
            try:
                role_enum = AgentRole(target_agent)
                await send_event(SupervisorEvent(
                    type=EventType.AGENT_STARTED, role=role_enum, content=""
                ))
                
                config = agent_config_repo.find_by_role(role_enum.value)
                prov_name = config.provider if config else settings.default_provider
                mod_name = config.model_name if config else settings.default_model
                llm_prov = get_llm_provider(prov_name)
                
                resp = await SubAgentRunner.run(
                    role=role_enum,
                    user_request=user_request,
                    llm_provider=llm_prov,
                    document_store=document_store,
                    model_name=mod_name
                )
                
                await send_event(SupervisorEvent(
                    type=EventType.AGENT_COMPLETED, role=role_enum, content=resp.content
                ))
                await send_event(SupervisorEvent(
                    type=EventType.DONE, role=None, content=resp.content
                ))
                
            except ValueError:
                debate_repo.update_status(debate_record.id, "aborted")
                await websocket.send_json({"type": "error", "content": f"Unknown agent role: {target_agent}"})
                await websocket.close(code=1003)
                return

    except WebSocketDisconnect:
        # Client disconnected mid-debate; gracefully exit.
        logger.info("WebSocket client disconnected")
        # Ensure status is updated to aborted if not completed
        try:
            record = debate_repo.find_by_id(debate_record.id)
            if record and record.status == "running":
                debate_repo.update_status(debate_record.id, "aborted")
        except Exception:
            pass
        
    except Exception as e:
        logger.exception("Error during debate WebSocket execution")
        try:
            debate_repo.update_status(debate_record.id, "aborted")
            await websocket.send_json({"type": "error", "content": str(e)})
            await websocket.close(code=1011)
        except Exception:
            pass
