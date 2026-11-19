"""
Unit tests for infrastructure LLM provider registry with injected LLMProviderConfig.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.infrastructure.llm import registry
from src.infrastructure.llm.anthropic_adapter import AnthropicAdapter
from src.infrastructure.llm.gemini_adapter import GeminiAdapter
from src.infrastructure.llm.openai_adapter import OpenAIAdapter
from src.infrastructure.llm.registry import (
    ConfiguredLLMProviderFactory,
    LLMProviderConfig,
    get_llm_provider,
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


def test_get_llm_provider_uses_injected_credentials(monkeypatch):
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

    get_llm_provider("gemini", config=cfg)
    get_llm_provider("openai", config=cfg)
    get_llm_provider("anthropic", config=cfg)

    assert calls == [
        ("gemini", {"api_key": "gem-injected", "project": "proj-123", "location": "us-central1"}),
        ("openai", {"api_key": "oai-injected"}),
        ("anthropic", {"api_key": "ant-injected"}),
    ]


def test_get_llm_provider_raises_on_missing_key_or_unknown_provider(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    empty_cfg = LLMProviderConfig()

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        get_llm_provider("openai", config=empty_cfg)

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        get_llm_provider("anthropic", config=empty_cfg)

    with pytest.raises(ValueError, match="Unknown LLM provider"):
        get_llm_provider("bedrock", config=empty_cfg)


def test_configured_llm_provider_factory_delegates_config(monkeypatch):
    for var in ("GEMINI_API_KEY", "GOOGLE_CLOUD_PROJECT", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    sentinel = MagicMock(spec=OpenAIAdapter)
    captured: list[dict] = []

    def _fake_openai(**kwargs):
        captured.append(kwargs)
        return sentinel

    monkeypatch.setattr(registry, "OpenAIAdapter", _fake_openai)

    factory = ConfiguredLLMProviderFactory(
        LLMProviderConfig(openai_api_key="oai-factory-key")
    )
    assert factory.is_configured("openai") is True
    assert factory.is_configured("anthropic") is False
    provider = factory("openai")
    assert provider is sentinel
    assert captured == [{"api_key": "oai-factory-key"}]
