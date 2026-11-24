"""
Tests for IMetricsService protocol and NoOpMetricsService.
Verifies compliance with hexagonal architecture requirements.
"""
import pytest
from src.domain.ports.metrics_service import IMetricsService
from src.infrastructure.observability.noop_metrics import NoOpMetricsService


def test_noop_metrics_service_implements_protocol():
    service = NoOpMetricsService()
    assert isinstance(service, IMetricsService)


def test_noop_metrics_service_methods_execute_without_error():
    service = NoOpMetricsService()
    # Ensure all methods run cleanly without exceptions or side-effects
    service.inc_websocket_connection(channel="debate")
    service.dec_websocket_connection(channel="debate")
    service.record_stt_duration(seconds=1.23, model="base")
    service.record_tts_duration(seconds=0.45, voice="ef_dora")
    service.inc_wake_word_detection(model="vosk")
    service.record_rag_query_duration(seconds=0.08, collection="default")
    service.inc_learning_notes_saved(status="success")
    service.inc_auth_failed_login(reason="invalid_password")

