"""
Infrastructure: LLM Provider Adapter Factory & Configuration

Provides constructor-injected configuration (``LLMProviderConfig``) and low-level
adapter instantiation helpers (``is_provider_configured``, ``create_llm_adapter``)
consumed by the composition root to populate the single ``LLMProviderRegistry``.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from src.domain.ports.llm_provider import ILLMProvider
from src.infrastructure.llm.anthropic_adapter import AnthropicAdapter
from src.infrastructure.llm.gemini_adapter import GeminiAdapter
from src.infrastructure.llm.local_llm_adapter import LocalLLMAdapter
from src.infrastructure.llm.openai_adapter import OpenAIAdapter

SUPPORTED_LLM_PROVIDERS: tuple[str, ...] = ("gemini", "openai", "anthropic", "local")


@dataclass(frozen=True)
class LLMProviderConfig:
    """Pure configuration value object injected from the composition root."""

    gemini_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_cloud_project: str | None = None
    google_cloud_location: str = "europe-west1"
    local_llm_base_url: str = ""
    local_llm_api_key: str = ""

    @classmethod
    def from_env(cls) -> LLMProviderConfig:
        """Fallback builder reading process environment variables (used when no config is injected)."""
        return cls(
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            google_cloud_project=os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("VERTEX_PROJECT_ID"),
            google_cloud_location=(
                os.getenv("GOOGLE_CLOUD_LOCATION")
                or os.getenv("VERTEX_LOCATION")
                or "europe-west1"
            ),
            local_llm_base_url=os.getenv("LOCAL_LLM_BASE_URL") or os.getenv("OLLAMA_BASE_URL") or "",
            local_llm_api_key=os.getenv("LOCAL_LLM_API_KEY") or "",
        )


def is_provider_configured(name: str, config: LLMProviderConfig | None = None) -> bool:
    """Check whether required credentials or env vars are configured for ``name``."""
    cfg = config if config is not None else LLMProviderConfig.from_env()
    provider_name = name.lower().strip()
    if provider_name == "gemini":
        return bool(
            cfg.gemini_api_key
            or cfg.google_cloud_project
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_CLOUD_PROJECT")
        )
    if provider_name == "openai":
        return bool(cfg.openai_api_key or os.getenv("OPENAI_API_KEY"))
    if provider_name == "anthropic":
        return bool(cfg.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY"))
    if provider_name == "local":
        return bool(
            cfg.local_llm_base_url.strip()
            or os.getenv("LOCAL_LLM_BASE_URL", "").strip()
            or os.getenv("OLLAMA_BASE_URL", "").strip()
        )
    return False


def create_llm_adapter(name: str, config: LLMProviderConfig | None = None) -> ILLMProvider:
    """
    Instantiate an ``ILLMProvider`` adapter for ``name`` using ``config``.

    Intended to be called from the composition root when building ``LLMProviderRegistry``
    so each configured provider adapter (and its underlying SDK client) is created once.

    Raises:
        ValueError: If provider is unknown or required API key is missing.
    """
    cfg = config if config is not None else LLMProviderConfig.from_env()
    provider_name = name.lower().strip()

    if provider_name == "gemini":
        return GeminiAdapter(
            api_key=cfg.gemini_api_key,
            project=cfg.google_cloud_project,
            location=cfg.google_cloud_location,
        )

    if provider_name == "openai":
        api_key = cfg.openai_api_key or os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not configured")
        return OpenAIAdapter(api_key=api_key)

    if provider_name == "anthropic":
        api_key = cfg.anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not configured")
        return AnthropicAdapter(api_key=api_key)

    if provider_name == "local":
        base_url = (
            cfg.local_llm_base_url.strip()
            or os.getenv("LOCAL_LLM_BASE_URL", "").strip()
            or os.getenv("OLLAMA_BASE_URL", "").strip()
        )
        if not base_url:
            raise ValueError("LOCAL_LLM_BASE_URL is not configured")
        api_key = cfg.local_llm_api_key or os.getenv("LOCAL_LLM_API_KEY", "")
        return LocalLLMAdapter(base_url=base_url, api_key=api_key)

    raise ValueError(f"Unknown LLM provider: '{name}'")
