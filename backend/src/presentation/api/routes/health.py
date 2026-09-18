"""
Presentation: Health route

GET /health — lightweight liveness check.
"""
from __future__ import annotations

from fastapi import APIRouter

from src.presentation.api.config import get_settings

router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict:
    settings = get_settings()
    return {"status": "ok", "version": settings.api_version}
