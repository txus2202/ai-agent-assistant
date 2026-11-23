"""
Composition Root Dependencies: LLM Registry, Configuration & Image Generation

Builds the singleton-per-app ``LLMProviderRegistry``, ``LLMProviderConfig``, and
``ImageGenerationService`` from presentation ``Settings`` so Infrastructure and
Application layers never import ``presentation/api/config.py`` directly.
"""
from __future__ import annotations

import logging
import os

from fastapi import Depends
from starlette.requests import HTTPConnection

from src.application.services.llm_provider_registry import LLMProviderRegistry
from src.domain.exceptions import LLMProviderError
from src.domain.ports.image_generator import IImageGenerator
from src.infrastructure.image_generation.service import ImageGenerationService
from src.infrastructure.llm.registry import (
    SUPPORTED_LLM_PROVIDERS,
    LLMProviderConfig,
    create_llm_adapter,
    is_provider_configured,
)
from src.presentation.api.config import Settings, get_settings

logger = logging.getLogger(__name__)


def _resolve_app_settings(
    connection: HTTPConnection | None = None,
    settings: Settings | None = None,
) -> Settings:
    app_state = getattr(getattr(connection, "app", None), "state", None) if connection is not None else None
    state_settings = getattr(app_state, "settings", None) if app_state is not None else None
    return state_settings or settings or get_settings()


def build_llm_provider_config(settings: Settings | None = None) -> LLMProviderConfig:
    """Build an immutable LLMProviderConfig from Settings."""
    cfg = settings or get_settings()
    return LLMProviderConfig(
        gemini_api_key=cfg.gemini_api_key,
        openai_api_key=cfg.openai_api_key,
        anthropic_api_key=cfg.anthropic_api_key,
        google_cloud_project=cfg.google_cloud_project,
        google_cloud_location=cfg.google_cloud_location,
        local_llm_base_url=cfg.local_llm_base_url,
        local_llm_api_key=cfg.local_llm_api_key,
    )


def build_llm_provider_registry(
    settings: Settings | None = None,
    *,
    config: LLMProviderConfig | None = None,
) -> LLMProviderRegistry:
    """Build and populate the application LLMProviderRegistry with configured adapters."""
    cfg = config if config is not None else build_llm_provider_config(settings)
    registry = LLMProviderRegistry()

    for provider_name in SUPPORTED_LLM_PROVIDERS:
        if not is_provider_configured(provider_name, config=cfg):
            continue
        try:
            adapter = create_llm_adapter(provider_name, config=cfg)
            registry.register(provider_name, adapter)
        except LLMProviderError as exc:
            logger.warning("Skipping LLM provider '%s' during registry initialization: %s", provider_name, exc)

    return registry


def get_llm_config(
    connection: HTTPConnection,
    settings: Settings = Depends(get_settings),
) -> LLMProviderConfig:
    """FastAPI dependency resolving LLMProviderConfig from app.state or Settings."""
    app_state = getattr(getattr(connection, "app", None), "state", None)
    existing = getattr(app_state, "llm_config", None) if app_state is not None else None
    if existing is not None:
        return existing
    resolved = build_llm_provider_config(_resolve_app_settings(connection, settings))
    if app_state is not None:
        app_state.llm_config = resolved
    return resolved


def get_llm_registry(
    connection: HTTPConnection,
    settings: Settings = Depends(get_settings),
) -> LLMProviderRegistry:
    """FastAPI dependency resolving the shared LLMProviderRegistry from app.state."""
    app_state = getattr(getattr(connection, "app", None), "state", None)
    existing = getattr(app_state, "llm_registry", None) if app_state is not None else None
    if existing is not None:
        return existing
    llm_cfg = getattr(app_state, "llm_config", None) if app_state is not None else None
    resolved = build_llm_provider_registry(_resolve_app_settings(connection, settings), config=llm_cfg)
    if app_state is not None:
        app_state.llm_registry = resolved
    return resolved


def build_image_generator(settings: Settings | None = None) -> IImageGenerator:
    """Build an IImageGenerator backed by ImageGenerationService using explicit config."""
    cfg = settings or get_settings()
    env_val = os.getenv("IMAGE_GENERATION_PROVIDER")
    if env_val is None:
        env_val = os.getenv("IMAGE_PROVIDER")
    provider_name = env_val if env_val is not None else cfg.image_generation_provider
    return ImageGenerationService(
        provider_name=provider_name,
        api_key=cfg.gemini_api_key or None,
        project=cfg.google_cloud_project,
    )


def get_image_generator(
    connection: HTTPConnection,
    settings: Settings = Depends(get_settings),
) -> IImageGenerator:
    """FastAPI dependency resolving IImageGenerator from app.state or building it."""
    app_state = getattr(getattr(connection, "app", None), "state", None)
    existing = getattr(app_state, "image_generator", None) if app_state is not None else None
    if existing is not None:
        return existing
    generator = build_image_generator(_resolve_app_settings(connection, settings))
    if app_state is not None:
        app_state.image_generator = generator
    return generator
