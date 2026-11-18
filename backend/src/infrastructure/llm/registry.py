"""
Infrastructure: LLM Provider Registry

Provides a centralized way to get an LLM provider instance by name,
handling API key initialization via config.
"""
from __future__ import annotations

import os
from src.domain.ports.llm_provider import ILLMProvider
from src.infrastructure.llm.gemini_adapter import GeminiAdapter
from src.infrastructure.llm.openai_adapter import OpenAIAdapter
from src.infrastructure.llm.anthropic_adapter import AnthropicAdapter
from src.presentation.api.config import get_settings


def is_provider_configured(name: str) -> bool:
    """
    Checks whether the required API key / environment variable is configured
    for the given provider.
    """
    settings = get_settings()
    provider_name = name.lower().strip()
    if provider_name == "gemini":
        return bool(
            settings.gemini_api_key
            or settings.google_cloud_project
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_CLOUD_PROJECT")
        )
    if provider_name == "openai":
        return bool(settings.openai_api_key or os.getenv("OPENAI_API_KEY"))
    if provider_name == "anthropic":
        return bool(settings.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY"))
    return False


def get_llm_provider(name: str) -> ILLMProvider:
    """
    Returns a configured ILLMProvider instance for the requested name.
    
    Args:
        name: One of 'gemini', 'openai', 'anthropic'
        
    Raises:
        ValueError: If the provider is unknown or if the required API key is missing.
    """
    settings = get_settings()
    provider_name = name.lower().strip()
    
    if provider_name == "gemini":
        # Do not fail early; GeminiAdapter has fallback logic for Vertex AI and Gemini CLI
        return GeminiAdapter(
            api_key=settings.gemini_api_key,
            project=settings.google_cloud_project,
            location=settings.google_cloud_location
        )
        
    elif provider_name == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is not configured")
        return OpenAIAdapter(api_key=settings.openai_api_key)
        
    elif provider_name == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is not configured")
        return AnthropicAdapter(api_key=settings.anthropic_api_key)
        
    else:
        raise ValueError(f"Unknown LLM provider: '{name}'")

