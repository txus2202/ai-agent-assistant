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
from src.domain.agents.supervisor_events import HITLResponse, SupervisorEvent
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
        provider = raw_start.get("provider", "gemini")
        model_name = raw_start.get("model_name", "gemini-1.5-flash")

        if not user_request:
            await websocket.send_json({"type": "error", "content": "user_request is required"})
            await websocket.close(code=1003)
            return

        # Setup dependencies
        settings = get_settings()
        
        try:
            llm_provider = get_llm_provider(provider)
        except Exception as e:
            await websocket.send_json({"type": "error", "content": f"Provider error: {str(e)}"})
            await websocket.close(code=1011)
            return

        # Using ChromaDB Document Store (Phase 2)
        document_store = ChromaDBDocumentStore(
            persist_directory=str(settings.chroma_persist_dir)
        )

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

        # Run the debate generator
        async for event in SupervisorAgent.run(
            user_request=user_request,
            llm_provider=llm_provider,
            document_store=document_store,
            model_name=model_name,
            hitl_callback=hitl_callback,
        ):
            await websocket.send_json(event_to_dict(event))
            
            # If debate is complete, we could trigger history saving here 
            # (to be implemented in History routes)

    except WebSocketDisconnect:
        # Client disconnected mid-debate; gracefully exit.
        logger.info("WebSocket client disconnected")
        
    except Exception as e:
        logger.exception("Error during debate WebSocket execution")
        try:
            await websocket.send_json({"type": "error", "content": str(e)})
            await websocket.close(code=1011)
        except Exception:
            pass
