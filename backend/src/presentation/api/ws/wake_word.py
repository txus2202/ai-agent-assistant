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
            # Receive raw bytes from the frontend
            data = await websocket.receive_bytes()
            
            # Process chunk
            detected = wake_word_service.process_chunk(data)
            
            if detected:
                logger.info("Wake word detected! Notifying client.")
                await websocket.send_text(json.dumps({"type": "WAKE_WORD_DETECTED"}))
                # Reset to avoid multiple rapid triggers
                wake_word_service.reset()
                
    except WebSocketDisconnect:
        logger.info("Wake-Word WebSocket disconnected by client")
    except Exception:
        logger.exception("Error in wake-word websocket")
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
