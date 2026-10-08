import asyncio
import io
from src.infrastructure.audio.local_audio_service import LocalAudioService
from src.presentation.api.config import get_settings

async def main():
    settings = get_settings()
    service = LocalAudioService(
        whisper_model_size=settings.whisper_model,
        kokoro_model_path=settings.kokoro_model_path,
        kokoro_voices_path=settings.kokoro_voices_path,
        kokoro_voice_name=settings.kokoro_voice_name
    )
    
    print("Synthesizing...")
    try:
        audio = await service.synthesize_speech("Hola, estoy probando que Atenea pueda hablar.")
        print(f"Success! {len(audio)} bytes generated.")
    except Exception as e:
        print("Error:", str(e))

asyncio.run(main())
