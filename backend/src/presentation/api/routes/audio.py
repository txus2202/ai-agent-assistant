import io
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response

from src.domain.entities.user import User
from src.infrastructure.audio.local_audio_service import LocalAudioService
from src.presentation.api.config import get_settings
from src.presentation.api.dependencies.auth import get_current_user

router = APIRouter(prefix="/audio", tags=["audio"])

# Singleton service reference
_audio_service: Optional[LocalAudioService] = None

def get_audio_service() -> LocalAudioService:
    global _audio_service
    if _audio_service is None:
        settings = get_settings()
        _audio_service = LocalAudioService(
            whisper_model_size=settings.whisper_model,
            kokoro_model_path=settings.kokoro_model_path,
            kokoro_voices_path=settings.kokoro_voices_path,
            kokoro_voice_name=settings.kokoro_voice_name,
            whisper_language=settings.whisper_language,
            whisper_initial_prompt=settings.whisper_initial_prompt,
            whisper_beam_size=settings.whisper_beam_size,
            whisper_threads=settings.whisper_threads,
            kokoro_omp_num_threads=settings.kokoro_omp_num_threads,
        )
    return _audio_service


@router.post(
    "/transcribe",
    responses={
        400: {"description": "No filename provided"},
        500: {"description": "Internal server error during transcription"},
    },
)
async def transcribe_audio(
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> dict:
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


@router.post(
    "/synthesize",
    responses={
        400: {"description": "Text is required"},
        500: {"description": "Internal server error during speech synthesis"},
    },
)
async def synthesize_audio(
    request: dict,
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """
    Synthesizes text to speech using Piper TTS.
    Returns a WAV file.
    """
    text = request.get("text", "")
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")

    try:
        service = get_audio_service()
        if "add_silence" in request:
            audio_bytes = await service.synthesize_speech(text, add_silence=bool(request["add_silence"]))
        else:
            audio_bytes = await service.synthesize_speech(text)
        return Response(content=audio_bytes, media_type="audio/wav")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
