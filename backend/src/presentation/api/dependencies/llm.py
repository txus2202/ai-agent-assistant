"""
Composition Root Dependencies: LLM Configuration & Image Generation

Builds infrastructure LLMProviderConfig, ConfiguredLLMProviderFactory, and
ImageGenerationService from presentation Settings so Infrastructure never imports
presentation/api/config.py directly.
"""
from __future__ import annotations

import os
from starlette.requests import HTTPConnection

from fastapi import Depends

from src.domain.ports.image_generator import IImageGenerator
from src.infrastructure.image_generation.service import ImageGenerationService
from src.infrastructure.llm.registry import ConfiguredLLMProviderFactory, LLMProviderConfig
from src.presentation.api.config import Settings, get_settings


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
    )


def build_llm_factory(settings: Settings | None = None) -> ConfiguredLLMProviderFactory:
    """Build a ConfiguredLLMProviderFactory bound to configured provider credentials."""
    return ConfiguredLLMProviderFactory(build_llm_provider_config(settings))


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

