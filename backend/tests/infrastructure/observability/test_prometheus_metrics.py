"""
Unit tests for PrometheusMetricsService.
Verifies metric recording, labels, gauge tracking, and fail-safe behavior.
"""
from unittest.mock import MagicMock

from src.domain.ports.metrics_service import IMetricsService
from src.infrastructure.observability.prometheus_metrics import PrometheusMetricsService


def test_prometheus_metrics_service_implements_protocol():
    service = PrometheusMetricsService()
    assert isinstance(service, IMetricsService)


def test_websocket_gauge_tracking():
    mock_gauge = MagicMock()
    service = PrometheusMetricsService()
    service._ws_active_connections = mock_gauge

    service.inc_websocket_connection(channel="debate")
    mock_gauge.labels.assert_called_with(channel="debate")
    mock_gauge.labels.return_value.inc.assert_called_once()

    service.dec_websocket_connection(channel="debate")
    mock_gauge.labels.assert_called_with(channel="debate")
    mock_gauge.labels.return_value.dec.assert_called_once()


def test_stt_transcription_histogram():
    mock_hist = MagicMock()
    service = PrometheusMetricsService()
    service._stt_transcription_seconds = mock_hist

    service.record_stt_duration(seconds=1.42, model="base")
    mock_hist.labels.assert_called_with(model="base")
    mock_hist.labels.return_value.observe.assert_called_with(1.42)


def test_tts_synthesis_histogram():
    mock_hist = MagicMock()
    service = PrometheusMetricsService()
    service._tts_synthesis_seconds = mock_hist

    service.record_tts_duration(seconds=0.35, voice="ef_dora")
    mock_hist.labels.assert_called_with(voice="ef_dora")
    mock_hist.labels.return_value.observe.assert_called_with(0.35)


def test_wake_word_counter():
    mock_counter = MagicMock()
    service = PrometheusMetricsService()
    service._wake_word_detections = mock_counter

    service.inc_wake_word_detection(model="vosk")
    mock_counter.labels.assert_called_with(model="vosk")
    mock_counter.labels.return_value.inc.assert_called_once()


def test_rag_query_histogram():
    mock_hist = MagicMock()
    service = PrometheusMetricsService()
    service._rag_query_seconds = mock_hist

    service.record_rag_query_duration(seconds=0.075, collection="obsidian_notes")
    mock_hist.labels.assert_called_with(collection="obsidian_notes")
    mock_hist.labels.return_value.observe.assert_called_with(0.075)


def test_learning_notes_saved_counter():
    mock_counter = MagicMock()
    service = PrometheusMetricsService()
    service._learning_notes_saved = mock_counter

    service.inc_learning_notes_saved(status="success")
    mock_counter.labels.assert_called_with(status="success")
    mock_counter.labels.return_value.inc.assert_called_once()


def test_auth_failed_login_counter():
    mock_counter = MagicMock()
    service = PrometheusMetricsService()
    service._auth_failed_logins = mock_counter

    service.inc_auth_failed_login(reason="invalid_password")
    mock_counter.labels.assert_called_with(reason="invalid_password")
    mock_counter.labels.return_value.inc.assert_called_once()


def test_fail_safe_guarantee_catches_all_exceptions():
    mock_gauge = MagicMock()
    mock_gauge.labels.side_effect = RuntimeError("Prometheus internal registry crash")

    service = PrometheusMetricsService()
    service._ws_active_connections = mock_gauge

    # Must NOT raise exception: fail-safe guarantee catches all internal errors
    service.inc_websocket_connection(channel="debate")

