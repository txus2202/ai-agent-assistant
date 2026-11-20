"""
Application Service: LLMProviderRegistry

Maps normalized provider names (e.g. "gemini", "openai", "anthropic") to shared
ILLMProvider adapter instances configured in the composition root (ADR-013).

This registry lives in the Application layer (not Infrastructure) because it
orchestrates only the ILLMProvider domain port without depending on any SDK.
"""
from __future__ import annotations

from src.domain.exceptions import ProviderNotRegisteredError
from src.domain.ports.llm_provider import ILLMProvider


class LLMProviderRegistry:
    """
    Runtime registry of ILLMProvider adapters keyed by normalized provider name.

    Usage::

        registry = LLMProviderRegistry()
        registry.register("gemini", GeminiAdapter(...))
        registry.register("openai", OpenAIAdapter(...))

        provider = registry.get("gemini")   # → GeminiAdapter
        provider.complete(prompt, model)
    """

    def __init__(self) -> None:
        self._providers: dict[str, ILLMProvider] = {}

    @staticmethod
    def _normalize_name(name: str) -> str:
        return name.lower().strip()

    def register(self, name: str, adapter: ILLMProvider) -> None:
        """Register (or replace) an adapter under the normalized ``name``."""
        key = self._normalize_name(name)
        if not key:
            raise ValueError("Provider name must not be empty.")
        self._providers[key] = adapter

    def is_registered(self, name: str) -> bool:
        """Return True if an adapter is registered for ``name``."""
        return self._normalize_name(name) in self._providers

    def __contains__(self, name: object) -> bool:
        if not isinstance(name, str):
            return False
        return self.is_registered(name)

    def get(self, name: str) -> ILLMProvider:
        """
        Return the adapter registered under ``name``.

        Raises:
            ProviderNotRegisteredError: if no adapter is registered for ``name``.
        """
        key = self._normalize_name(name)
        if key not in self._providers:
            raise ProviderNotRegisteredError(
                provider=name,
                available=self.available(),
            )
        return self._providers[key]

    def available(self) -> list[str]:
        """Return a list of all registered provider names in registration order."""
        return list(self._providers.keys())
