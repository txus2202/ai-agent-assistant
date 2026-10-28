import logging
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.infrastructure.audio.wake_word_service import WakeWordService

from typing import Any, Mapping

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws/audio", tags=["Audio"])

# Initialize the wake word service globally so it's loaded once.
# The WakeWordService uses Vosk locally.
wake_word_service = WakeWordService()



async def _send_detection_event(websocket: WebSocket, detected: Any) -> None:
    if getattr(detected, "command", None):
        cmd = detected.command
        if cmd == "silence":
            logger.info("Silence voice command detected! Notifying client.")
            await websocket.send_text(json.dumps({
                "type": "SILENCE_VOICE_COMMAND",
            }))
        else:
            logger.info(f"HITL voice command detected: {cmd}! Notifying client.")
            await websocket.send_text(json.dumps({
                "type": "HITL_VOICE_COMMAND",
                "command": cmd,
            }))

    else:
        role = getattr(detected, "agent_role", None) or "supervisor"
        name = getattr(detected, "display_name", None) or role
        logger.info(f"Wake word detected for {name} ({role})! Notifying client.")
        await websocket.send_text(json.dumps({
            "type": "WAKE_WORD_DETECTED",
            "agent_role": role,
            "display_name": name,
        }))
    wake_word_service.reset()


def _handle_control_text(text: str) -> None:
    try:
        payload = json.loads(text)
        if payload.get("type") in ("RESET", "reset"):
            wake_word_service.reset()
            logger.info("Wake-Word service reset via client control command")
    except Exception:
        pass


async def _process_incoming_message(websocket: WebSocket, message: Mapping[str, Any]) -> None:
    if message.get("type") == "websocket.disconnect":
        raise WebSocketDisconnect(message.get("code", 1000))

    data_bytes = message.get("bytes")
    if data_bytes:
        detected = wake_word_service.process_chunk(data_bytes)
        if detected:
            await _send_detection_event(websocket, detected)
        return

    data_text = message.get("text")
    if data_text:
        _handle_control_text(data_text)


@router.websocket("/wake-word")
async def wake_word_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for continuous audio streaming.
    Expects raw 16kHz Int16 PCM audio chunks.
    Sends {"type": "WAKE_WORD_DETECTED"} when the wake word is detected.
    """
    await websocket.accept()
    logger.info("Client connected to Wake-Word stream")
    wake_word_service.reset()
    
    try:
        while True:
            message = await websocket.receive()
            await _process_incoming_message(websocket, message)
    except WebSocketDisconnect:
        logger.info("Wake-Word WebSocket disconnected by client")
    except Exception:
        logger.exception("Error in wake-word websocket")
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
