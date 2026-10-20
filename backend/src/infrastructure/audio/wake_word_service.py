import os
import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from vosk import Model, KaldiRecognizer

from src.domain.agents.sub_agent_profiles import get_all_profiles

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WakeWordDetection:
    """Result of wake-word processing."""
    detected: bool
    agent_role: str | None = None
    display_name: str | None = None

    def __bool__(self) -> bool:
        return self.detected


class WakeWordService:
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
            role_val = profile.role.value

            # Primary normalized name (e.g. "atenea", "hermes", "icaro", "hefesto")
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
        model_path = os.path.join(os.path.dirname(__file__), "..", "models", "vosk", "vosk-model-small-es-0.42")
        print(f"[WW] Initializing WakeWordService with Vosk model: {model_path}")
        
        try:
            self.model = Model(model_path)
            self.recognizer = KaldiRecognizer(self.model, 16000)
            self.is_initialized = True
            print("[WW] Vosk model loaded successfully!")
        except Exception:
            logger.exception("Failed to load Vosk model")
            self.model = None
            self.recognizer = None
            self.is_initialized = True
        
    def process_chunk(self, audio_chunk_pcm_16khz: bytes) -> WakeWordDetection:
        """
        Process a chunk of 16kHz Int16 PCM audio.
        Returns WakeWordDetection indicating whether a registered agent wake word was detected.
        """
        self._initialize_model()
        if not self.recognizer:
            return WakeWordDetection(detected=False)

        # Feed audio to Vosk
        if self.recognizer.AcceptWaveform(audio_chunk_pcm_16khz):
            res = json.loads(self.recognizer.Result())
            text = res.get("text", "")
        else:
            res = json.loads(self.recognizer.PartialResult())
            text = res.get("partial", "")

        if not text:
            return WakeWordDetection(detected=False)

        norm_text = self._normalize_text(text)
        logger.debug(f"[WW] Vosk decoded: '{text}' (normalized: '{norm_text}')")

        # Check for registered agent trigger keywords
        for trigger, (role, display_name) in self._agent_triggers.items():
            pattern = rf"\b{re.escape(trigger)}\b"
            if re.search(pattern, norm_text) or re.search(pattern, text.lower()):
                print(f"[WW] Wake word '{trigger}' detected for agent '{display_name}' ({role}) in text: '{text}'")
                return WakeWordDetection(
                    detected=True,
                    agent_role=role,
                    display_name=display_name
                )
            
        return WakeWordDetection(detected=False)
        
    def reset(self):
        """Reset the internal state of the wake word models (useful after detection)."""
        self._initialize_model()
        if self.recognizer:
            self.recognizer.Reset()

