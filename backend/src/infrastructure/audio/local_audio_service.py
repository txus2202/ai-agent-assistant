import asyncio
import io
import wave
from pathlib import Path
from typing import BinaryIO

from faster_whisper import WhisperModel
import soundfile as sf
import numpy as np
import av
from kokoro_onnx import Kokoro

# Patch PyAV open to ignore 'metadata_errors' which was removed in newer versions
# but is still passed by faster-whisper <= 1.2.x, causing a TypeError.
original_av_open = av.open
def patched_av_open(*args, **kwargs):
    kwargs.pop("metadata_errors", None)
    return original_av_open(*args, **kwargs)
av.open = patched_av_open

from src.domain.ports.audio_service import IAudioService


class LocalAudioService(IAudioService):
    """
    Local implementation of audio transcription (faster-whisper) 
    and synthesis (kokoro-onnx).
    """

    def __init__(self, whisper_model_size: str, kokoro_model_path: Path, kokoro_voices_path: Path, kokoro_voice_name: str):
        self.whisper_model_size = whisper_model_size
        self.kokoro_model_path = kokoro_model_path
        self.kokoro_voices_path = kokoro_voices_path
        self.kokoro_voice_name = kokoro_voice_name

        # We load Whisper model lazily to avoid blocking startup.
        self.whisper_model = None
        
        # Load Kokoro lazily
        self.kokoro = None

    def _get_whisper_model(self) -> WhisperModel:
        if self.whisper_model is None:
            print(f"Loading Whisper model '{self.whisper_model_size}'...")
            self.whisper_model = WhisperModel(self.whisper_model_size, device="cpu", compute_type="int8")
        return self.whisper_model

    def _get_kokoro(self) -> Kokoro:
        if self.kokoro is None:
            if not self.kokoro_model_path.exists():
                raise FileNotFoundError(f"Kokoro model not found at {self.kokoro_model_path}")
            if not self.kokoro_voices_path.exists():
                raise FileNotFoundError(f"Kokoro voices not found at {self.kokoro_voices_path}")
                
            print(f"Loading Kokoro from '{self.kokoro_model_path}'...")
            self.kokoro = Kokoro(str(self.kokoro_model_path), str(self.kokoro_voices_path))
        return self.kokoro

    async def transcribe_audio(self, audio_file: BinaryIO) -> str:
        """
        Transcribe audio to text.
        """
        def _transcribe():
            model = self._get_whisper_model()
            segments, _ = model.transcribe(
                audio_file, 
                beam_size=5,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
                initial_prompt="This is a conversation in Spanish and English. Hola, ¿cómo estás? Hello, how are you?"
            )
            text = " ".join([segment.text for segment in segments])
            return text.strip()
        
        # Run in thread to not block event loop
        return await asyncio.to_thread(_transcribe)

    async def synthesize_speech(self, text: str) -> bytes:
        """
        Synthesize text to speech using Kokoro ONNX.
        """
        def _synthesize():
            kokoro_tts = self._get_kokoro()
            
            # Generate audio samples
            samples, sample_rate = kokoro_tts.create(
                text,
                voice=self.kokoro_voice_name,
                speed=1.0,
                lang="es"
            )
            
            # Add 300ms of silence at the beginning to prevent browser cutoff
            silence_samples = int(0.3 * sample_rate)
            silence = np.zeros(silence_samples, dtype=samples.dtype)
            samples = np.concatenate((silence, samples))
            
            # Write samples to an in-memory WAV buffer
            buf = io.BytesIO()
            sf.write(buf, samples, sample_rate, format='WAV')
            
            return buf.getvalue()

        # Run in thread to not block event loop
        return await asyncio.to_thread(_synthesize)
