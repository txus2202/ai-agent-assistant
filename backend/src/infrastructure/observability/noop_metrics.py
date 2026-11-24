"""
Infrastructure: NoOpMetricsService
Null Object implementation of IMetricsService for testing, offline, or fallback environments.
"""
from __future__ import annotations

from src.domain.ports.metrics_service import IMetricsService


class NoOpMetricsService(IMetricsService):
    """Silent metrics provider that performs no operations."""

    def inc_websocket_connection(self, channel: str) -> None:
        pass

    def dec_websocket_connection(self, channel: str) -> None:
        pass

    def record_stt_duration(self, seconds: float, model: str = "base") -> None:
        pass

    def record_tts_duration(self, seconds: float, voice: str = "default") -> None:
        pass

    def inc_wake_word_detection(self, model: str = "vosk") -> None:
        pass

    def record_rag_query_duration(self, seconds: float, collection: str = "default") -> None:
        pass

    def inc_learning_notes_saved(self, status: str = "success") -> None:
        pass

    def inc_auth_failed_login(self, reason: str = "invalid_credentials") -> None:
        pass

