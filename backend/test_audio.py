import asyncio
import io
import wave
from pathlib import Path

from src.infrastructure.audio.local_audio_service import LocalAudioService
from src.presentation.api.config import get_settings

async def main():
    settings = get_settings()
    service = LocalAudioService(
        whisper_model_size=settings.whisper_model,
        piper_model_path=settings.piper_voice_model
    )

    print("Testing synthesis...")
    wav_bytes = await service.synthesize_speech("Hola Atenea. ¿Cómo estás?")
    
    with open("test_output.wav", "wb") as f:
        f.write(wav_bytes)
    print(f"Saved test_output.wav ({len(wav_bytes)} bytes)")

    print("Testing transcription...")
    with open("test_output.wav", "rb") as f:
        # Load into memory buffer
        buf = io.BytesIO(f.read())
        buf.name = "test_output.wav"
        
        text = await service.transcribe_audio(buf)
        print("Transcription:", text)

if __name__ == "__main__":
    asyncio.run(main())
