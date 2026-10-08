import io
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from src.infrastructure.audio.local_audio_service import LocalAudioService
from src.presentation.api.config import get_settings

router = APIRouter(prefix="/audio", tags=["audio"])

# Singleton service reference
_audio_service: LocalAudioService = None

def get_audio_service() -> LocalAudioService:
    global _audio_service
    if _audio_service is None:
        settings = get_settings()
        _audio_service = LocalAudioService(
            whisper_model_size=settings.whisper_model,
            kokoro_model_path=settings.kokoro_model_path,
            kokoro_voices_path=settings.kokoro_voices_path,
            kokoro_voice_name=settings.kokoro_voice_name
        )
    return _audio_service


@router.post("/transcribe")
async def transcribe_audio(file: Annotated[UploadFile, File(...)]) -> dict:
    """
    Transcribes audio to text using local Whisper.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    try:
        # Read file into memory (it's small voice chunks, should be fine)
        audio_bytes = await file.read()
        audio_io = io.BytesIO(audio_bytes)
        audio_io.name = file.filename # Whisper might need extension hint if any

        service = get_audio_service()
        transcription = await service.transcribe_audio(audio_io)
        
        return {"text": transcription}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/synthesize")
async def synthesize_audio(request: dict) -> Response:
    """
    Synthesizes text to speech using Piper TTS.
    Returns a WAV file.
    """
    text = request.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    try:
        service = get_audio_service()
        audio_bytes = await service.synthesize_speech(text)
        return Response(content=audio_bytes, media_type="audio/wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
