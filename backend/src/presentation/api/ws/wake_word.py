import logging
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.infrastructure.audio.wake_word_service import WakeWordService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws/audio", tags=["Audio"])

# Initialize the wake word service globally so it's loaded once.
# The WakeWordService uses Vosk locally.
wake_word_service = WakeWordService()

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
            if message.get("type") == "websocket.disconnect":
                raise WebSocketDisconnect(message.get("code", 1000))

            if "bytes" in message and message["bytes"]:
                data = message["bytes"]
                # Process chunk
                detected = wake_word_service.process_chunk(data)
                
                if detected:
                    if getattr(detected, "command", None):
                        cmd = detected.command
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
                    # Reset to avoid multiple rapid triggers
                    wake_word_service.reset()

            elif "text" in message and message["text"]:
                try:
                    payload = json.loads(message["text"])
                    if payload.get("type") in ("RESET", "reset"):
                        wake_word_service.reset()
                        logger.info("Wake-Word service reset via client control command")
                except Exception:
                    pass
                
    except WebSocketDisconnect:
        logger.info("Wake-Word WebSocket disconnected by client")
    except Exception:
        logger.exception("Error in wake-word websocket")
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
