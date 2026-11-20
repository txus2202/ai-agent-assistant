"""
RED Tests: Observability API Routes (Feature: feature_observability.md)
"""
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from src.presentation.api.app import create_app
from src.domain.ports.observability_service import SystemMetrics


from src.domain.entities.user import User
from src.presentation.api.dependencies.auth import get_current_user


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: User(
        id="usr-test", username="testuser", password_hash="h", is_admin=False
    )
    return TestClient(app)


def test_observability_unauthenticated():
    app = create_app()
    c = TestClient(app)
    assert c.get("/observability/stats").status_code == 401


def test_get_observability_stats_endpoint(client):
    mock_metrics = SystemMetrics(
        cpu_percent=45.0,
        memory_percent=60.5,
        cluster_status="HEALTHY",
        active_agents_count=2,
    )

    with patch(
        "src.presentation.api.routes.observability.get_observability_service"
    ) as mock_get_service:
        mock_service = MagicMock()
        mock_service.get_system_metrics.return_value = mock_metrics
        mock_get_service.return_value = mock_service

        response = client.get("/observability/stats")
        assert response.status_code == 200
        data = response.json()

        assert data["cluster_status"] == "HEALTHY"
        assert data["cpu_percent"] == 45.0
        assert data["memory_percent"] == 60.5
        assert data["active_agents_count"] == 2
        assert "langfuse_metrics_enabled" in data
        assert "langfuse_dashboard_url" in data
        assert data["langfuse_dashboard_url"] == "http://localhost:3000"


def test_get_observability_stats_reflects_settings(client):
    mock_metrics = SystemMetrics(
        cpu_percent=10.0,
        memory_percent=20.0,
        cluster_status="HEALTHY",
        active_agents_count=0,
    )

    with patch("src.presentation.api.routes.observability.get_observability_service") as mock_get_service, \
         patch("src.presentation.api.routes.observability.get_settings") as mock_settings:
        mock_service = MagicMock()
        mock_service.get_system_metrics.return_value = mock_metrics
        mock_get_service.return_value = mock_service

        mock_config = MagicMock()
        mock_config.langfuse_metrics_enabled = False
        mock_settings.return_value = mock_config

        res = client.get("/observability/stats")
        assert res.status_code == 200
        assert res.json()["langfuse_metrics_enabled"] is False

        mock_config.langfuse_metrics_enabled = True
        res_enabled = client.get("/observability/stats")
        assert res_enabled.status_code == 200
        assert res_enabled.json()["langfuse_metrics_enabled"] is True

