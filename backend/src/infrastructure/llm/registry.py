"""
Infrastructure: LLM Provider Registry

Provides constructor-injected configuration (``LLMProviderConfig``) and factory
functions to instantiate ``ILLMProvider`` adapters without importing Presentation
settings.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from src.domain.ports.llm_provider import ILLMProvider
from src.infrastructure.llm.anthropic_adapter import AnthropicAdapter
from src.infrastructure.llm.gemini_adapter import GeminiAdapter
from src.infrastructure.llm.openai_adapter import OpenAIAdapter


@dataclass(frozen=True)
class LLMProviderConfig:
    """Pure configuration value object injected from the composition root."""

    gemini_api_key: str = ""
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    google_cloud_project: str | None = None
    google_cloud_location: str = "europe-west1"

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
        )


class ConfiguredLLMProviderFactory:
    """Constructor-injected factory encapsulating provider credentials."""

    def __init__(self, config: LLMProviderConfig) -> None:
        self._config = config

    def is_configured(self, name: str) -> bool:
        return is_provider_configured(name, config=self._config)

    def get(self, name: str) -> ILLMProvider:
        return get_llm_provider(name, config=self._config)

    def __call__(self, name: str) -> ILLMProvider:
        return self.get(name)


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
    return False


def get_llm_provider(name: str, config: LLMProviderConfig | None = None) -> ILLMProvider:
    """
    Return a configured ``ILLMProvider`` instance for ``name``.

    Args:
        name: One of 'gemini', 'openai', 'anthropic'.
        config: Explicit credentials/project config injected from composition root.

    Raises:
        ValueError: If provider is unknown or required API key is missing.
    """
    cfg = config if config is not None else LLMProviderConfig.from_env()
    provider_name = name.lower().strip()

    if provider_name == "gemini":
        # Do not fail early; GeminiAdapter supports Vertex AI and Gemini CLI fallback
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

    raise ValueError(f"Unknown LLM provider: '{name}'")
