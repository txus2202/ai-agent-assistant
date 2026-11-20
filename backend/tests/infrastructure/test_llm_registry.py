"""
Unit tests for infrastructure LLM adapter factory helpers with injected LLMProviderConfig.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.infrastructure.llm import registry
from src.infrastructure.llm.anthropic_adapter import AnthropicAdapter
from src.infrastructure.llm.gemini_adapter import GeminiAdapter
from src.infrastructure.llm.openai_adapter import OpenAIAdapter
from src.infrastructure.llm.registry import (
    SUPPORTED_LLM_PROVIDERS,
    LLMProviderConfig,
    create_llm_adapter,
    is_provider_configured,
)


def test_is_provider_configured_uses_injected_config(monkeypatch):
    for var in ("GEMINI_API_KEY", "GOOGLE_CLOUD_PROJECT", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    cfg = LLMProviderConfig(
        gemini_api_key="gem-key",
        openai_api_key="",
        anthropic_api_key="ant-key",
    )
    assert is_provider_configured("gemini", config=cfg) is True
    assert is_provider_configured("anthropic", config=cfg) is True
    assert is_provider_configured("openai", config=cfg) is False
    assert is_provider_configured("unknown", config=cfg) is False


def test_create_llm_adapter_uses_injected_credentials(monkeypatch):
    for var in ("GEMINI_API_KEY", "GOOGLE_CLOUD_PROJECT", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    calls: list[tuple[str, dict]] = []

    def _capture(tag: str, cls_ref):
        def _factory(**kwargs):
            calls.append((tag, kwargs))
            return MagicMock(spec=cls_ref)
        return _factory

    monkeypatch.setattr(registry, "GeminiAdapter", _capture("gemini", GeminiAdapter))
    monkeypatch.setattr(registry, "OpenAIAdapter", _capture("openai", OpenAIAdapter))
    monkeypatch.setattr(registry, "AnthropicAdapter", _capture("anthropic", AnthropicAdapter))

    cfg = LLMProviderConfig(
        gemini_api_key="gem-injected",
        openai_api_key="oai-injected",
        anthropic_api_key="ant-injected",
        google_cloud_project="proj-123",
        google_cloud_location="us-central1",
    )

    create_llm_adapter("gemini", config=cfg)
    create_llm_adapter("openai", config=cfg)
    create_llm_adapter("anthropic", config=cfg)

    assert calls == [
        ("gemini", {"api_key": "gem-injected", "project": "proj-123", "location": "us-central1"}),
        ("openai", {"api_key": "oai-injected"}),
        ("anthropic", {"api_key": "ant-injected"}),
    ]


def test_create_llm_adapter_raises_on_missing_key_or_unknown_provider(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    empty_cfg = LLMProviderConfig()

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        create_llm_adapter("openai", config=empty_cfg)

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        create_llm_adapter("anthropic", config=empty_cfg)

    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_llm_adapter("bedrock", config=empty_cfg)


def test_registry_retires_legacy_global_factory_helpers():
    assert SUPPORTED_LLM_PROVIDERS == ("gemini", "openai", "anthropic")
    assert not hasattr(registry, "get_llm_provider")
    assert not hasattr(registry, "ConfiguredLLMProviderFactory")
