import os
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from vosk import Model, KaldiRecognizer  # type: ignore[import-untyped]

from src.domain.agents.sub_agent_profiles import get_all_profiles

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WakeWordDetection:
    """Result of wake-word processing."""
    detected: bool
    agent_role: str | None = None
    display_name: str | None = None
    command: str | None = None

    def __bool__(self) -> bool:
        return self.detected


class WakeWordService:
    _HITL_TRIGGERS: dict[str, str] = {
        "aceptar": "approve",
        "aprobar": "approve",
        "adelante": "approve",
        "conforme": "approve",
        "rechazar": "reject",
        "denegar": "reject",
        "cancela": "reject",
        "cancelar": "reject",
        "descarta": "reject",
        "descartar": "reject",
        "refinar": "refine",
        "corregir": "refine",
        "cambiar": "refine",
        "modificar": "refine",
        "ajustar": "refine",
        "consolidar": "consolidate",
        "consolida": "consolidate",
        "resumir": "consolidate",
        "resumen": "consolidate",
        "finalizar": "finish",
        "terminar": "finish",
        "detener": "finish",
        "parar": "finish",
        "para": "finish",
        "concluir": "finish",
        "fin": "finish",
        "desviar": "divert",
        "bifurcar": "divert",
        "derivar": "divert",
        "delegar": "divert",
        "reintentar": "retry",
        "reintenta": "retry",
        "repetir": "retry",
        "reintento": "retry",
        "retry": "retry",
    }

    _SILENCE_TRIGGERS: dict[str, str] = {
        "silencio": "silence",
        "silenciar": "silence",
        "calla": "silence",
        "callate": "silence",
        "cállate": "silence",
    }


    def __init__(self):
        """
        Initialize the WakeWord service using Vosk and dynamic agent profiles.
        """
        self.is_initialized = False
        self.model = None
        self.recognizer = None
        self._agent_triggers: dict[str, tuple[str, str]] = self._build_agent_triggers()

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Lowercase and remove accents/diacritics for robust matching."""
        nfkd = unicodedata.normalize('NFKD', text)
        return ''.join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()

    def _build_agent_triggers(self) -> dict[str, tuple[str, str]]:
        """
        Dynamically extracts all agent wake words and aliases from SubAgentProfile registry.
        Maps trigger keyword -> (agent_role_value, display_name).
        """
        triggers: dict[str, tuple[str, str]] = {}
        profiles = get_all_profiles()

        for profile in profiles:
            display_name = profile.display_name
            role_val = profile.id

            # Primary normalized name from profile display name
            norm_name = self._normalize_text(display_name)
            triggers[norm_name] = (role_val, display_name)

            # Raw lowercased name if different (e.g. "ícaro")
            raw_lower = display_name.lower().strip()
            if raw_lower != norm_name:
                triggers[raw_lower] = (role_val, display_name)

            # Phonetic aliases configured on the profile (e.g. Vosk phonetic decodings)
            for alias in profile.phonetic_aliases:
                norm_alias = self._normalize_text(alias)
                triggers[norm_alias] = (role_val, display_name)
                raw_alias = alias.lower().strip()
                if raw_alias != norm_alias:
                    triggers[raw_alias] = (role_val, display_name)

        return triggers

    def _initialize_model(self):
        if self.is_initialized:
            return
        
        # Path to Vosk model
        env_path = os.environ.get("VOSK_MODEL_PATH")
        candidates = [
            env_path,
            "/app/models/vosk-model-small-es-0.42",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "vosk", "vosk-model-small-es-0.42")),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "models", "vosk-model-small-es-0.42")),
        ]
        model_path = next((p for p in candidates if p and os.path.exists(p)), env_path or candidates[2])
        print(f"[WW] Initializing WakeWordService with Vosk model: {model_path}")
        
        try:
            self.model = Model(model_path)
            self.recognizer = KaldiRecognizer(self.model, 16000)
            self.is_initialized = True
            print("[WW] Vosk model loaded successfully!")
        except Exception:
            logger.exception("Failed to load Vosk model at %s", model_path)
            self.model = None
            self.recognizer = None
            self.is_initialized = True
        
    def _decode_audio_text(self, audio_chunk_pcm_16khz: bytes) -> str:
        if not self.recognizer:
            return ""
        if self.recognizer.AcceptWaveform(audio_chunk_pcm_16khz):
            res = json.loads(self.recognizer.Result())
            return res.get("text", "")
        res = json.loads(self.recognizer.PartialResult())
        return res.get("partial", "")

    @staticmethod
    def _matches_keyword(keyword: str, norm_text: str, raw_lower: str) -> bool:
        pattern = rf"\b{re.escape(keyword)}\b"
        return bool(re.search(pattern, norm_text) or re.search(pattern, raw_lower))

    def _match_silence(self, norm_text: str, raw_lower: str, text: str) -> WakeWordDetection | None:
        for trigger, cmd in self._SILENCE_TRIGGERS.items():
            if self._matches_keyword(trigger, norm_text, raw_lower):
                print(f"[WW] Silence voice command '{trigger}' detected in text: '{text}'")
                return WakeWordDetection(detected=True, command=cmd)
        return None

    def _match_agent(self, norm_text: str, raw_lower: str, text: str) -> WakeWordDetection | None:
        for trigger, (role, display_name) in self._agent_triggers.items():
            if self._matches_keyword(trigger, norm_text, raw_lower):
                print(f"[WW] Wake word '{trigger}' detected for agent '{display_name}' ({role}) in text: '{text}'")
                return WakeWordDetection(detected=True, agent_role=role, display_name=display_name)
        return None

    def _match_hitl(self, norm_text: str, raw_lower: str, text: str) -> WakeWordDetection | None:
        for trigger, cmd in self._HITL_TRIGGERS.items():
            if self._matches_keyword(trigger, norm_text, raw_lower):
                print(f"[WW] HITL voice command '{trigger}' -> '{cmd}' detected in text: '{text}'")
                return WakeWordDetection(detected=True, command=cmd)
        return None

    def process_chunk(self, audio_chunk_pcm_16khz: bytes) -> WakeWordDetection:
        """
        Process a chunk of 16kHz Int16 PCM audio.
        Returns WakeWordDetection indicating whether a registered agent wake word was detected.
        """
        self._initialize_model()
        text = self._decode_audio_text(audio_chunk_pcm_16khz)
        if not text:
            return WakeWordDetection(detected=False)

        norm_text = self._normalize_text(text)
        raw_lower = text.lower()
        logger.debug(f"[WW] Vosk decoded: '{text}' (normalized: '{norm_text}')")

        detection = (
            self._match_silence(norm_text, raw_lower, text)
            or self._match_agent(norm_text, raw_lower, text)
            or self._match_hitl(norm_text, raw_lower, text)
        )
        return detection or WakeWordDetection(detected=False)

        
    def reset(self):
        """Reset the internal state of the wake word models (useful after detection)."""
        self._initialize_model()
        if self.recognizer:
            self.recognizer.Reset()

