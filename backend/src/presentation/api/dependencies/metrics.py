"""
Presentation Dependency: Metrics
Provides access to IMetricsService via FastAPI dependency injection.
"""
from __future__ import annotations

from fastapi import Request
from src.domain.ports.metrics_service import IMetricsService
from src.infrastructure.observability.noop_metrics import NoOpMetricsService


def get_metrics_service(request: Request) -> IMetricsService:
    """Retrieve IMetricsService from application state or fallback to NoOpMetricsService."""
    return getattr(request.app.state, "metrics_service", None) or NoOpMetricsService()

