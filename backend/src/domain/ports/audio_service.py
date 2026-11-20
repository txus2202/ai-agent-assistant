"""
Domain Port: IAudioService
"""
from __future__ import annotations

from typing import BinaryIO, Protocol, runtime_checkable


@runtime_checkable
class IAudioService(Protocol):
    """
    Port for audio transcription and synthesis.
    """

    async def transcribe_audio(self, audio_file: BinaryIO) -> str:
        """
        Transcribe audio to text.

        Args:
            audio_file: A file-like object containing the audio data.

        Returns:
            The transcribed text.
        """
        ...

    async def synthesize_speech(self, text: str, add_silence: bool = False) -> bytes:
        """
        Synthesize text to speech.

        Args:
            text: The text to synthesize.

        Returns:
            The generated audio data (WAV format).
        """
        ...
