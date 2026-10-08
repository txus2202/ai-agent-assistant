from abc import ABC, abstractmethod
from typing import BinaryIO

class IAudioService(ABC):
    """
    Port for audio transcription and synthesis.
    """

    @abstractmethod
    async def transcribe_audio(self, audio_file: BinaryIO) -> str:
        """
        Transcribe audio to text.
        
        Args:
            audio_file: A file-like object containing the audio data.
            
        Returns:
            The transcribed text.
        """
        pass

    @abstractmethod
    async def synthesize_speech(self, text: str) -> bytes:
        """
        Synthesize text to speech.
        
        Args:
            text: The text to synthesize.
            
        Returns:
            The generated audio data (WAV format).
        """
        pass
