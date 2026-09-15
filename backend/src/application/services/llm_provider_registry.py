"""
Application Service: LLMProviderRegistry

Maps provider name strings (e.g. "gemini", "openai") to ILLMProvider instances.
Configured at application startup (e.g. in main.py or a DI container).

This registry lives in the Application layer (not Infrastructure) because it
orchestrates domain ports — it must not depend on any specific SDK (ADR-013).
"""
from __future__ import annotations

from src.domain.exceptions import ProviderNotRegisteredError
from src.domain.ports.llm_provider import ILLMProvider


class LLMProviderRegistry:
    """
    Runtime registry of ILLMProvider adapters keyed by provider name.

    Usage::

        registry = LLMProviderRegistry()
        registry.register("gemini", GeminiAdapter())
        registry.register("openai", OpenAIAdapter())

        provider = registry.get("gemini")   # → GeminiAdapter
        provider.complete(prompt, model)
    """

    def __init__(self) -> None:
        self._providers: dict[str, ILLMProvider] = {}

    def register(self, name: str, adapter: ILLMProvider) -> None:
        """Register (or replace) an adapter under ``name``."""
        self._providers[name] = adapter

    def get(self, name: str) -> ILLMProvider:
        """
        Return the adapter registered under ``name``.

        Raises:
            ProviderNotRegisteredError: if no adapter is registered for ``name``.
        """
        if name not in self._providers:
            raise ProviderNotRegisteredError(
                provider=name,
                available=self.available(),
            )
        return self._providers[name]

    def available(self) -> list[str]:
        """Return a list of all registered provider names."""
        return list(self._providers.keys())
