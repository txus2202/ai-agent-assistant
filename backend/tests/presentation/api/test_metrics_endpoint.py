"""
Integration tests for Prometheus metrics integration and /metrics route.
"""
from unittest.mock import MagicMock
import pytest

from src.infrastructure.observability.prometheus_metrics import PrometheusMetricsService
from src.presentation.api.config import Settings
from src.presentation.api.dependencies.metrics import get_metrics_service


@pytest.mark.anyio
async def test_metrics_service_dependency_fallback():
    # When not set in state, fallback is NoOp
    mock_request = MagicMock()
    mock_request.app.state.metrics_service = None
    service = get_metrics_service(mock_request)
    assert service is not None
    # Method calls work without exception
    service.inc_websocket_connection("debate")


@pytest.mark.anyio
async def test_metrics_service_state_retrieval():
    metrics_svc = PrometheusMetricsService()
    mock_request = MagicMock()
    mock_request.app.state.metrics_service = metrics_svc
    service = get_metrics_service(mock_request)
    assert service is metrics_svc


def test_settings_metrics_enabled_defaults_to_true(monkeypatch):
    monkeypatch.delenv("METRICS_ENABLED", raising=False)
    settings = Settings()
    assert settings.metrics_enabled is True


def test_settings_metrics_enabled_can_be_disabled_via_env(monkeypatch):
    monkeypatch.setenv("METRICS_ENABLED", "false")
    settings = Settings()
    assert settings.metrics_enabled is False


def test_settings_metrics_enabled_can_be_disabled_via_flag():
    settings = Settings(metrics_enabled=False)
    assert settings.metrics_enabled is False
