"""
RED Tests — LLM Provider Adapters (Feature: feature_llm_adapters.md)

Layer: Infrastructure

Strategy: All SDK imports are mocked via sys.modules + monkeypatch.
No real API calls are made. Each adapter is tested in isolation.

Scenarios covered:
  - Successful complete() → returns str
  - SDK exception → wrapped as LLMProviderError
  - Missing API key → LLMProviderError at construction
  - Missing SDK package → LLMProviderError at construction
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.domain.exceptions import LLMProviderError


# ===========================================================================
# Helpers
# ===========================================================================

class DummyCountResp:
    total_tokens = 100

def _make_genai_mock(response_text: str = "Gemini response") -> MagicMock:
    """Build a mock google.genai module that returns response_text."""
    mock = MagicMock()
    mock.Client.return_value.models.generate_content.return_value.text = response_text
    
    mock.Client.return_value.models.count_tokens.return_value = DummyCountResp()
    return mock


def _make_openai_mock(response_text: str = "OpenAI response") -> MagicMock:
    """Build a mock openai module."""
    mock = MagicMock()
    choice = MagicMock()
    choice.message.content = response_text
    mock.OpenAI.return_value.chat.completions.create.return_value.choices = [choice]
    return mock


def _make_anthropic_mock(response_text: str = "Anthropic response") -> MagicMock:
    """Build a mock anthropic module."""
    mock = MagicMock()
    content_block = MagicMock()
    content_block.text = response_text
    mock.Anthropic.return_value.messages.create.return_value.content = [content_block]
    return mock


# ===========================================================================
# GeminiAdapter
# ===========================================================================

class TestGeminiAdapter:
    @pytest.fixture(autouse=True)
    def mock_genai(self, monkeypatch):
        """Inject mock google.genai before each test."""
        mock = _make_genai_mock()
        monkeypatch.setitem(sys.modules, "google", MagicMock(genai=mock))
        monkeypatch.setitem(sys.modules, "google.genai", mock)
        self._mock_genai = mock

    def test_complete_returns_string(self):
        from src.infrastructure.llm.gemini_adapter import GeminiAdapter

        adapter = GeminiAdapter(api_key="test-key")
        result = adapter.complete("Hello", "gemini-3.6-flash")

        assert isinstance(result, str)
        assert result == "Gemini response"

    def test_complete_with_context_caching(self):
        from src.infrastructure.llm.gemini_adapter import GeminiAdapter

        # Simulate large prompt >= 32768 tokens
        count_mock = MagicMock()
        count_mock.total_tokens = 35000
        self._mock_genai.Client.return_value.models.count_tokens.return_value = count_mock

        cache_mock = MagicMock()
        cache_mock.name = "cachedContents/test-cache-id"
        self._mock_genai.Client.return_value.caches.create.return_value = cache_mock

        adapter = GeminiAdapter(api_key="test-key")
        result = adapter.complete("Very large prompt", "gemini-2.5-flash")

        assert result == "Gemini response"
        self._mock_genai.Client.return_value.caches.create.assert_called_once_with(
            model="gemini-2.5-flash",
            config={
                "contents": ["Very large prompt"],
                "ttl": "3600s",
            },
        )
        self._mock_genai.Client.return_value.caches.delete.assert_called_once_with(
            name="cachedContents/test-cache-id"
        )

    def test_complete_image_returns_string(self, tmp_path: Path):
        from src.infrastructure.llm.gemini_adapter import GeminiAdapter

        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n")

        adapter = GeminiAdapter(api_key="test-key")
        result = adapter.complete_image("Describe diagram", img_file, "gemini-2.5-flash")

        assert isinstance(result, str)
        assert result == "Gemini response"

    def test_complete_wraps_sdk_exception_as_llm_provider_error(self):
        from src.infrastructure.llm.gemini_adapter import GeminiAdapter

        self._mock_genai.Client.return_value.models.generate_content.side_effect = RuntimeError("quota exceeded")

        adapter = GeminiAdapter(api_key="test-key")
        with pytest.raises(LLMProviderError, match="quota exceeded"):
            adapter.complete("Hello", "gemini-3.6-flash")

    def test_missing_api_key_raises_llm_provider_error(self, monkeypatch):
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        from src.infrastructure.llm.gemini_adapter import GeminiAdapter
        
        # When no API key is provided, the code tries _genai.Client().
        # We need the mock to raise an exception here to simulate no ADC auth.
        self._mock_genai.Client.side_effect = Exception("No auth")

        with pytest.raises(LLMProviderError, match="No auth configured"):
            GeminiAdapter()  # no key passed, no env var

    def test_missing_sdk_raises_llm_provider_error(self, monkeypatch):
        """If google-genai is not installed, construction raises LLMProviderError."""
        monkeypatch.delitem(sys.modules, "google.genai", raising=False)
        monkeypatch.delitem(sys.modules, "google", raising=False)

        # Cause the import to fail
        import builtins
        real_import = builtins.__import__

        def _fail_genai(name, *args, **kwargs):
            if "google" in name:
                raise ImportError(f"No module named '{name}'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _fail_genai)

        # Remove cached module so lazy import is re-triggered
        from src.infrastructure.llm import gemini_adapter
        import importlib
        importlib.reload(gemini_adapter)

        with pytest.raises(LLMProviderError, match="google-genai"):
            gemini_adapter.GeminiAdapter(api_key="test-key")


# ===========================================================================
# OpenAIAdapter
# ===========================================================================

class TestOpenAIAdapter:
    @pytest.fixture(autouse=True)
    def mock_openai(self, monkeypatch):
        mock = _make_openai_mock()
        monkeypatch.setitem(sys.modules, "openai", mock)
        self._mock_openai = mock

    def test_complete_returns_string(self):
        from src.infrastructure.llm.openai_adapter import OpenAIAdapter

        adapter = OpenAIAdapter(api_key="test-key")
        result = adapter.complete("Hello", "gpt-4o-mini")

        assert isinstance(result, str)
        assert result == "OpenAI response"

    def test_complete_image_returns_string(self, tmp_path: Path):
        from src.infrastructure.llm.openai_adapter import OpenAIAdapter

        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n")

        adapter = OpenAIAdapter(api_key="test-key")
        result = adapter.complete_image("Describe diagram", img_file, "gpt-4o")

        assert isinstance(result, str)
        assert result == "OpenAI response"

    def test_complete_wraps_sdk_exception_as_llm_provider_error(self):
        from src.infrastructure.llm.openai_adapter import OpenAIAdapter

        self._mock_openai.OpenAI.return_value.chat.completions.create.side_effect = RuntimeError("rate limit")

        adapter = OpenAIAdapter(api_key="test-key")
        with pytest.raises(LLMProviderError, match="rate limit"):
            adapter.complete("Hello", "gpt-4o-mini")

    def test_missing_api_key_raises_llm_provider_error(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        from src.infrastructure.llm.openai_adapter import OpenAIAdapter

        with pytest.raises(LLMProviderError, match="OPENAI_API_KEY"):
            OpenAIAdapter()


# ===========================================================================
# AnthropicAdapter
# ===========================================================================

class TestAnthropicAdapter:
    @pytest.fixture(autouse=True)
    def mock_anthropic(self, monkeypatch):
        mock = _make_anthropic_mock()
        monkeypatch.setitem(sys.modules, "anthropic", mock)
        self._mock_anthropic = mock

    def test_complete_returns_string(self):
        from src.infrastructure.llm.anthropic_adapter import AnthropicAdapter

        adapter = AnthropicAdapter(api_key="test-key")
        result = adapter.complete("Hello", "claude-3-haiku-20240307")

        assert isinstance(result, str)
        assert result == "Anthropic response"

    def test_complete_wraps_sdk_exception_as_llm_provider_error(self):
        from src.infrastructure.llm.anthropic_adapter import AnthropicAdapter

        self._mock_anthropic.Anthropic.return_value.messages.create.side_effect = RuntimeError("overloaded")

        adapter = AnthropicAdapter(api_key="test-key")
        with pytest.raises(LLMProviderError, match="overloaded"):
            adapter.complete("Hello", "claude-3-haiku-20240307")

    def test_missing_api_key_raises_llm_provider_error(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        from src.infrastructure.llm.anthropic_adapter import AnthropicAdapter

        with pytest.raises(LLMProviderError, match="ANTHROPIC_API_KEY"):
            AnthropicAdapter()
