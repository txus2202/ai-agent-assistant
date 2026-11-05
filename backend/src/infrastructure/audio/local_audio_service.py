import asyncio
import io
import os
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
from src.infrastructure.audio.phonetic_normalizer import SpanishTechPhoneticNormalizer


class LocalAudioService(IAudioService):
    """
    Local implementation of audio transcription (faster-whisper) 
    and synthesis (kokoro-onnx).
    """

    def __init__(
        self,
        whisper_model_size: str,
        kokoro_model_path: Path,
        kokoro_voices_path: Path,
        kokoro_voice_name: str,
        whisper_language: str = "es",
        whisper_initial_prompt: str | None = None,
        whisper_beam_size: int = 5,
        whisper_threads: int = 4,
        kokoro_omp_num_threads: int | None = None,
    ):
        self.whisper_model_size = whisper_model_size
        self.kokoro_model_path = kokoro_model_path
        self.kokoro_voices_path = kokoro_voices_path
        self.kokoro_voice_name = kokoro_voice_name
        self.whisper_language = whisper_language
        self.whisper_beam_size = whisper_beam_size
        self.whisper_threads = whisper_threads
        self.kokoro_omp_num_threads = kokoro_omp_num_threads
        self.whisper_initial_prompt = whisper_initial_prompt or (
            "Conversación técnica en castellano sobre desarrollo de software, arquitectura de sistemas e infraestructura. "
            "Uso frecuente de términos técnicos, herramientas, patrones y nombres en inglés: "
            "backend, frontend, fullstack, microservicios, API REST, GraphQL, WebSocket, gRPC, "
            "Docker, Kubernetes, CI/CD, DevOps, DevSecOps, cloud-native, serverless, AWS, Azure, GCP, "
            "SQLite, PostgreSQL, Redis, Kafka, ChromaDB, FastAPI, Python, TypeScript, JavaScript, Vue, React, "
            "Node.js, Next.js, Vite, CQRS, Event-Driven, DDD, clean architecture, arquitectura hexagonal, "
            "Zero-Trust, STRIDE, SPOF, Langfuse, OpenTelemetry, Prometheus, Grafana, HITL, Pull Request, "
            "merge, commit, branch, deploy, clúster, endpoints, logs, métricas, tracing."
        )

        self.phonetic_normalizer = SpanishTechPhoneticNormalizer()

        # We load Whisper model lazily to avoid blocking startup.
        self.whisper_model = None
        
        # Load Kokoro lazily
        self.kokoro = None

    def _get_whisper_model(self) -> WhisperModel:
        if self.whisper_model is None:
            print(f"Loading Whisper model '{self.whisper_model_size}' with {self.whisper_threads} threads...")
            self.whisper_model = WhisperModel(
                self.whisper_model_size,
                device="cpu",
                compute_type="int8",
                cpu_threads=self.whisper_threads,
            )
        return self.whisper_model

    def _resolve_omp_threads(self) -> int | None:
        threads_env = os.environ.get("KOKORO_OMP_NUM_THREADS")
        if threads_env and threads_env.strip().isdigit():
            return int(threads_env.strip())
        if self.kokoro_omp_num_threads is not None and self.kokoro_omp_num_threads > 0:
            return self.kokoro_omp_num_threads
        return None

    def _init_kokoro_instance(self) -> Kokoro:
        if not self.kokoro_model_path.exists():
            raise FileNotFoundError(f"Kokoro model not found at {self.kokoro_model_path}")
        if not self.kokoro_voices_path.exists():
            raise FileNotFoundError(f"Kokoro voices not found at {self.kokoro_voices_path}")

        omp_threads = self._resolve_omp_threads()
        if omp_threads:
            print(f"Loading Kokoro from '{self.kokoro_model_path}' with {omp_threads} ONNX intra_op threads...")
            import onnxruntime as rt
            sess_options = rt.SessionOptions()
            sess_options.intra_op_num_threads = omp_threads
            sess_options.inter_op_num_threads = 1
            session = rt.InferenceSession(
                str(self.kokoro_model_path),
                sess_options=sess_options,
                providers=["CPUExecutionProvider"],
            )
            return Kokoro.from_session(session, str(self.kokoro_voices_path))

        print(f"Loading Kokoro from '{self.kokoro_model_path}' (default ONNX thread pool)...")
        return Kokoro(str(self.kokoro_model_path), str(self.kokoro_voices_path))

    def _get_kokoro(self) -> Kokoro:
        if self.kokoro is None:
            self.kokoro = self._init_kokoro_instance()
        return self.kokoro

    def _build_initial_prompt(self) -> str:
        prompt = self.whisper_initial_prompt
        try:
            from src.domain.agents.sub_agent_profiles import get_all_profiles
            names = [p.display_name for p in get_all_profiles() if p.display_name]
            if names:
                prompt = f"{prompt.rstrip('.')} Nombres de agentes: {', '.join(names)}."
        except Exception:
            pass
        return prompt

    async def transcribe_audio(self, audio_file: BinaryIO) -> str:
        """
        Transcribe audio to text.
        """
        prompt = self._build_initial_prompt()

        def _transcribe():
            model = self._get_whisper_model()
            segments, _ = model.transcribe(
                audio_file, 
                language=self.whisper_language,
                beam_size=self.whisper_beam_size,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
                initial_prompt=prompt,
            )
            text = " ".join([segment.text for segment in segments])
            return text.strip()
        
        # Run in thread to not block event loop
        return await asyncio.to_thread(_transcribe)

    async def synthesize_speech(self, text: str, add_silence: bool = False) -> bytes:
        """
        Synthesize text to speech using Kokoro ONNX.
        Applies Spanish technical phonetic normalization and strips Markdown before synthesis.
        """
        def _synthesize():
            kokoro_tts = self._get_kokoro()
            
            # Normalize technical terms and strip markdown for natural Spanish pronunciation
            spoken_text = self.phonetic_normalizer.normalize(text) or text.strip()

            # Generate audio samples
            samples, sample_rate = kokoro_tts.create(
                spoken_text,
                voice=self.kokoro_voice_name,
                speed=1.0,
                lang="es"
            )
            
            # Add initial silence if explicitly requested (e.g., for isolated one-off playbacks)
            if add_silence:
                silence_samples = int(0.15 * sample_rate)
                silence = np.zeros(silence_samples, dtype=samples.dtype)
                samples = np.concatenate((silence, samples))
            
            # Write samples to an in-memory WAV buffer
            buf = io.BytesIO()
            sf.write(buf, samples, sample_rate, format='WAV')
            
            return buf.getvalue()

        # Run in thread to not block event loop
        return await asyncio.to_thread(_synthesize)
