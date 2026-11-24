"""
Domain Port: IMetricsService
Defines protocol for system-wide performance and operational telemetry.
Hexagonal architecture port to decouple Domain/Application from concrete telemetry providers.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class IMetricsService(Protocol):
    """
    Port for system-wide performance and operational metrics collection.
    Follows fail-safe execution: failures in metric reporting must never raise to caller.
    """

    def inc_websocket_connection(self, channel: str) -> None:
        """Increment active WebSocket connections for a given channel (e.g. debate, voice)."""
        ...

    def dec_websocket_connection(self, channel: str) -> None:
        """Decrement active WebSocket connections for a given channel."""
        ...

    def record_stt_duration(self, seconds: float, model: str = "base") -> None:
        """Record audio transcription latency in seconds for STT engine."""
        ...

    def record_tts_duration(self, seconds: float, voice: str = "default") -> None:
        """Record audio synthesis latency in seconds for TTS engine."""
        ...

    def inc_wake_word_detection(self, model: str = "vosk") -> None:
        """Increment counter for detected wake word keyword."""
        ...

    def record_rag_query_duration(self, seconds: float, collection: str = "default") -> None:
        """Record ChromaDB vector similarity query latency in seconds."""
        ...

    def inc_learning_notes_saved(self, status: str = "success") -> None:
        """Increment counter for Obsidian Vault notes saved or consolidated."""
        ...

    def inc_auth_failed_login(self, reason: str = "invalid_credentials") -> None:
        """Increment counter for failed authentication attempts."""
        ...

