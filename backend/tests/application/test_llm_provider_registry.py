"""
RED Tests — LLMProviderRegistry (Feature: feature_llm_adapters.md)

Layer: Application

Scenarios:
  - register() + get() returns correct adapter
  - get() raises ProviderNotRegisteredError for unknown provider
  - available() returns all registered names
  - RunAgentTask integration: registry resolves provider at runtime
"""
from __future__ import annotations

import pytest

from src.domain.exceptions import LLMProviderError, ProviderNotRegisteredError
from src.domain.ports.llm_provider import ILLMProvider


# ---------------------------------------------------------------------------
# Test double
# ---------------------------------------------------------------------------

class FakeAdapter(ILLMProvider):
    def __init__(self, name: str = "fake"):
        self.name = name

    def list_models(self, probe: bool = True) -> list[dict[str, str]]:
        return [{"id": "test", "name": "Test"}]

    def complete(self, prompt: str, model_name: str) -> str:
        return f"{self.name}:{model_name}:{prompt}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLLMProviderRegistry:
    def test_register_and_get_returns_adapter(self):
        from src.application.services.llm_provider_registry import LLMProviderRegistry

        registry = LLMProviderRegistry()
        adapter = FakeAdapter("gemini")
        registry.register("gemini", adapter)

        assert registry.get("gemini") is adapter

    def test_get_unknown_provider_raises_provider_not_registered_error(self):
        from src.application.services.llm_provider_registry import LLMProviderRegistry

        registry = LLMProviderRegistry()
        registry.register("gemini", FakeAdapter())

        with pytest.raises(ProviderNotRegisteredError) as exc_info:
            registry.get("openai")

        assert "openai" in str(exc_info.value)
        assert "gemini" in str(exc_info.value)  # hint shows available providers

    def test_available_returns_all_registered_names(self):
        from src.application.services.llm_provider_registry import LLMProviderRegistry

        registry = LLMProviderRegistry()
        registry.register("gemini", FakeAdapter())
        registry.register("openai", FakeAdapter())

        available = registry.available()

        assert set(available) == {"gemini", "openai"}

    def test_available_returns_empty_for_new_registry(self):
        from src.application.services.llm_provider_registry import LLMProviderRegistry

        registry = LLMProviderRegistry()
        assert registry.available() == []

    def test_register_overwrites_existing_provider(self):
        from src.application.services.llm_provider_registry import LLMProviderRegistry

        registry = LLMProviderRegistry()
        original = FakeAdapter("original")
        replacement = FakeAdapter("replacement")
        registry.register("gemini", original)
        registry.register("gemini", replacement)

        assert registry.get("gemini") is replacement

    def test_error_message_includes_available_providers(self):
        from src.application.services.llm_provider_registry import LLMProviderRegistry

        registry = LLMProviderRegistry()
        registry.register("anthropic", FakeAdapter())
        registry.register("gemini", FakeAdapter())

        with pytest.raises(ProviderNotRegisteredError) as exc_info:
            registry.get("openai")

        err = exc_info.value
        assert err.provider == "openai"
        assert set(err.available) == {"anthropic", "gemini"}

    def test_normalizes_provider_names_and_supports_membership_check(self):
        from src.application.services.llm_provider_registry import LLMProviderRegistry

        registry = LLMProviderRegistry()
        adapter = FakeAdapter("gemini")
        registry.register(" Gemini ", adapter)

        assert registry.is_registered("GEMINI") is True
        assert "gemini" in registry
        assert "openai" not in registry
        assert registry.get("GeMiNi") is adapter
        assert registry.available() == ["gemini"]
        assert not hasattr(registry, "list_all_models")
