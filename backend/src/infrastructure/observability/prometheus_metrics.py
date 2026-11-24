"""
Infrastructure: PrometheusMetricsService
Prometheus / OpenMetrics adapter implementing IMetricsService port.
Provides non-intrusive, fail-safe metric instrumentation for Atenea.
"""
from __future__ import annotations

import logging
from typing import Any

from src.domain.ports.metrics_service import IMetricsService

logger = logging.getLogger(__name__)

# Fallback definitions if prometheus_client is unavailable
try:
    from prometheus_client import Counter, Gauge, Histogram, REGISTRY
    PROMETHEUS_AVAILABLE = True
except ImportError:
    Counter = Any  # type: ignore[misc, assignment]
    Gauge = Any  # type: ignore[misc, assignment]
    Histogram = Any  # type: ignore[misc, assignment]
    REGISTRY = None  # type: ignore[assignment]
    PROMETHEUS_AVAILABLE = False


def _get_or_create_metric(collector_cls: type, name: str, documentation: str, labelnames: list[str], **kwargs: Any) -> Any:
    """Safely get existing metric from REGISTRY or create a new one to prevent duplication errors."""
    if not PROMETHEUS_AVAILABLE or REGISTRY is None:
        return None

    # Check if already registered
    collector = REGISTRY._names_to_collectors.get(name)
    if collector is not None:
        return collector

    try:
        return collector_cls(name, documentation, labelnames=labelnames, **kwargs)
    except Exception as exc:
        logger.debug("Failed to register metric '%s': %s", name, exc)
        return None


class PrometheusMetricsService(IMetricsService):
    """
    OpenMetrics / Prometheus telemetry adapter.
    Implements all operations with strict fail-safe guarantees.
    """

    def __init__(self) -> None:
        self.is_enabled = PROMETHEUS_AVAILABLE

        # Capa 1: Transporte WebSockets
        self._ws_active_connections = _get_or_create_metric(
            Gauge,
            "atenea_websocket_active_connections",
            "Active WebSocket connections by channel",
            labelnames=["channel"],
        )

        # Capa 3: Pipeline de Voz y Audio (Intel N100)
        self._stt_transcription_seconds = _get_or_create_metric(
            Histogram,
            "atenea_stt_transcription_seconds",
            "Audio transcription duration in seconds (Faster-Whisper)",
            labelnames=["model"],
            buckets=(0.1, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 8.0),
        )

        self._tts_synthesis_seconds = _get_or_create_metric(
            Histogram,
            "atenea_tts_synthesis_seconds",
            "Speech synthesis duration in seconds (Kokoro-ONNX)",
            labelnames=["voice"],
            buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 3.0),
        )

        self._wake_word_detections = _get_or_create_metric(
            Counter,
            "atenea_wake_word_detections_total",
            "Total wake word keyword detections (Vosk)",
            labelnames=["model"],
        )

        # Capa 4: RAG, Memoria y Seguridad
        self._rag_query_seconds = _get_or_create_metric(
            Histogram,
            "atenea_rag_query_duration_seconds",
            "ChromaDB vector similarity search duration in seconds",
            labelnames=["collection"],
            buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
        )

        self._learning_notes_saved = _get_or_create_metric(
            Counter,
            "atenea_learning_notes_saved_total",
            "Total consolidated notes saved to Obsidian Vault",
            labelnames=["status"],
        )

        self._auth_failed_logins = _get_or_create_metric(
            Counter,
            "atenea_auth_failed_logins_total",
            "Total failed authentication attempts by reason",
            labelnames=["reason"],
        )

        # Pre-initialize default label series to 0 so Prometheus exports them immediately at startup
        self._preinitialize_default_labels()

    def _preinitialize_default_labels(self) -> None:
        """Pre-initialize common label dimensions so Netdata/Prometheus discover metrics at boot."""
        try:
            if self._ws_active_connections is not None:
                self._ws_active_connections.labels(channel="debate")
            if self._stt_transcription_seconds is not None:
                self._stt_transcription_seconds.labels(model="base")
            if self._tts_synthesis_seconds is not None:
                self._tts_synthesis_seconds.labels(voice="default")
            if self._wake_word_detections is not None:
                self._wake_word_detections.labels(model="vosk")
            if self._rag_query_seconds is not None:
                self._rag_query_seconds.labels(collection="default")
            if self._learning_notes_saved is not None:
                self._learning_notes_saved.labels(status="success")
            if self._auth_failed_logins is not None:
                self._auth_failed_logins.labels(reason="invalid_credentials")
        except Exception as exc:
            logger.debug("Failed to pre-initialize Prometheus default metric labels: %s", exc)

    def inc_websocket_connection(self, channel: str) -> None:
        try:
            if self._ws_active_connections is not None:
                self._ws_active_connections.labels(channel=channel).inc()
        except Exception as exc:
            logger.debug("Error recording inc_websocket_connection: %s", exc)

    def dec_websocket_connection(self, channel: str) -> None:
        try:
            if self._ws_active_connections is not None:
                self._ws_active_connections.labels(channel=channel).dec()
        except Exception as exc:
            logger.debug("Error recording dec_websocket_connection: %s", exc)

    def record_stt_duration(self, seconds: float, model: str = "base") -> None:
        try:
            if self._stt_transcription_seconds is not None:
                self._stt_transcription_seconds.labels(model=model).observe(seconds)
        except Exception as exc:
            logger.debug("Error recording record_stt_duration: %s", exc)

    def record_tts_duration(self, seconds: float, voice: str = "default") -> None:
        try:
            if self._tts_synthesis_seconds is not None:
                self._tts_synthesis_seconds.labels(voice=voice).observe(seconds)
        except Exception as exc:
            logger.debug("Error recording record_tts_duration: %s", exc)

    def inc_wake_word_detection(self, model: str = "vosk") -> None:
        try:
            if self._wake_word_detections is not None:
                self._wake_word_detections.labels(model=model).inc()
        except Exception as exc:
            logger.debug("Error recording inc_wake_word_detection: %s", exc)

    def record_rag_query_duration(self, seconds: float, collection: str = "default") -> None:
        try:
            if self._rag_query_seconds is not None:
                self._rag_query_seconds.labels(collection=collection).observe(seconds)
        except Exception as exc:
            logger.debug("Error recording record_rag_query_duration: %s", exc)

    def inc_learning_notes_saved(self, status: str = "success") -> None:
        try:
            if self._learning_notes_saved is not None:
                self._learning_notes_saved.labels(status=status).inc()
        except Exception as exc:
            logger.debug("Error recording inc_learning_notes_saved: %s", exc)

    def inc_auth_failed_login(self, reason: str = "invalid_credentials") -> None:
        try:
            if self._auth_failed_logins is not None:
                self._auth_failed_logins.labels(reason=reason).inc()
        except Exception as exc:
            logger.debug("Error recording inc_auth_failed_login: %s", exc)

