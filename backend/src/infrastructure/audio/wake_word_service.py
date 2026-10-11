import os
import json
import logging
from vosk import Model, KaldiRecognizer

logger = logging.getLogger(__name__)

class WakeWordService:
    def __init__(self):
        """
        Initialize the WakeWord service using Vosk.
        """
        self.is_initialized = False
        self.model = None
        self.recognizer = None

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
        
    def process_chunk(self, audio_chunk_pcm_16khz: bytes) -> bool:
        """
        Process a chunk of 16kHz Int16 PCM audio.
        Returns True if the wake word is detected in this chunk.
        """
        self._initialize_model()
        if not self.recognizer:
            return False

        # Feed audio to Vosk
        if self.recognizer.AcceptWaveform(audio_chunk_pcm_16khz):
            res = json.loads(self.recognizer.Result())
            text = res.get("text", "").lower()
        else:
            res = json.loads(self.recognizer.PartialResult())
            text = res.get("partial", "").lower()

        # Check for the wake word
        if "atenea" in text:
            print(f"[WW] Wake word 'atenea' detected in text: '{text}'")
            return True
            
        return False
        
    def reset(self):
        """Reset the internal state of the wake word models (useful after detection)."""
        self._initialize_model()
        if self.recognizer:
            self.recognizer.Reset()
