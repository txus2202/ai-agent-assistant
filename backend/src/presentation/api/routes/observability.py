"""
Presentation: Observability Routes
Endpoints for system observability metrics and telemetry.
"""
from __future__ import annotations

from typing import Any
from fastapi import APIRouter, Depends

from src.domain.entities.user import User
from src.domain.ports.observability_port import IObservabilityService
from src.infrastructure.observability.langfuse_adapter import LangfuseObservabilityAdapter
from src.presentation.api.config import get_settings
from src.presentation.api.dependencies.auth import get_current_user

router = APIRouter(prefix="/observability", tags=["observability"])

_observability_service: IObservabilityService | None = None


def get_observability_service() -> IObservabilityService:
    global _observability_service
    if _observability_service is None:
        settings = get_settings()
        _observability_service = LangfuseObservabilityAdapter(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.effective_langfuse_host,
            enabled=settings.langfuse_metrics_enabled,
        )
    return _observability_service


def reset_observability_service() -> None:
    """Reset the cached singleton. Used in tests."""
    global _observability_service
    _observability_service = None


@router.get("/stats")
async def get_stats(
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve real-time cluster health, CPU/memory telemetry, and active agent counts."""
    service = get_observability_service()
    metrics = service.get_system_metrics()
    settings = get_settings()
    return {
        "cluster_status": metrics.cluster_status,
        "cpu_percent": metrics.cpu_percent,
        "memory_percent": metrics.memory_percent,
        "active_agents_count": metrics.active_agents_count,
        "additional_stats": metrics.additional_stats,
        "langfuse_metrics_enabled": settings.langfuse_metrics_enabled,
    }

