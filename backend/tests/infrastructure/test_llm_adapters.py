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

    def test_complete_skips_count_tokens_and_single_use_cache_round_trips(self):
        from src.infrastructure.llm.gemini_adapter import GeminiAdapter

        self._mock_genai.Client.return_value.models.count_tokens.reset_mock()
        self._mock_genai.Client.return_value.caches.create.reset_mock()
        self._mock_genai.Client.return_value.caches.delete.reset_mock()

        adapter = GeminiAdapter(api_key="test-key")
        small_res = adapter.complete("Short prompt", "gemini-2.5-flash")
        large_res = adapter.complete("x" * 130_000, "gemini-2.5-flash")

        assert small_res == "Gemini response"
        assert large_res == "Gemini response"
        self._mock_genai.Client.return_value.models.count_tokens.assert_not_called()
        self._mock_genai.Client.return_value.caches.create.assert_not_called()
        self._mock_genai.Client.return_value.caches.delete.assert_not_called()
        assert self._mock_genai.Client.return_value.models.generate_content.call_count == 2

    def test_concurrent_complete_isolates_usage_per_task_and_thread(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        from src.infrastructure.llm.gemini_adapter import GeminiAdapter

        barrier = threading.Barrier(2, timeout=2.0)

        def _generate_side_effect(model, contents):
            resp = MagicMock()
            if contents == "prompt-A":
                resp.text = "reply-A"
                resp.usage_metadata = MagicMock(
                    prompt_token_count=100,
                    candidates_token_count=20,
                    total_token_count=120,
                )
            else:
                resp.text = "reply-B"
                resp.usage_metadata = MagicMock(
                    prompt_token_count=500,
                    candidates_token_count=50,
                    total_token_count=550,
                )
            barrier.wait()
            return resp

        self._mock_genai.Client.return_value.models.generate_content.side_effect = _generate_side_effect
        adapter = GeminiAdapter(api_key="test-key")
        assert not hasattr(adapter, "_last_usage")

        def _run_call(prompt: str):
            completion = adapter.complete_with_usage(prompt, "gemini-2.5-flash")
            return completion.content, completion.usage, adapter.get_last_usage()

        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_a = pool.submit(_run_call, "prompt-A")
            fut_b = pool.submit(_run_call, "prompt-B")
            res_a = fut_a.result(timeout=3.0)
            res_b = fut_b.result(timeout=3.0)

        assert res_a == (
            "reply-A",
            {"input": 100, "output": 20, "total": 120},
            {"input": 100, "output": 20, "total": 120},
        )
        assert res_b == (
            "reply-B",
            {"input": 500, "output": 50, "total": 550},
            {"input": 500, "output": 50, "total": 550},
        )
        assert not hasattr(adapter, "_last_usage")

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

    def test_list_models_probes_with_count_tokens_and_prunes_deprecated(self):
        from src.infrastructure.llm.gemini_adapter import GeminiAdapter

        m_active = MagicMock()
        m_active.name = "models/gemini-1.5-flash"
        m_active.display_name = "Gemini 1.5 Flash"
        m_active.supported_generation_methods = ["generateContent"]

        m_deprecated = MagicMock()
        m_deprecated.name = "models/gemini-2.5-flash"
        m_deprecated.display_name = "Gemini 2.5 Flash"
        m_deprecated.supported_generation_methods = ["generateContent"]

        m_embedding = MagicMock()
        m_embedding.name = "models/text-embedding-004"
        m_embedding.display_name = "Embedding 004"
        m_embedding.supported_generation_methods = ["embedContent"]

        self._mock_genai.Client.return_value.models.list.return_value = [
            m_active,
            m_deprecated,
            m_embedding,
        ]

        def _count_tokens_side_effect(model, contents):
            if "2.5-flash" in model:
                raise RuntimeError("404 NOT_FOUND: model is no longer available")
            return DummyCountResp()

        self._mock_genai.Client.return_value.models.count_tokens.side_effect = _count_tokens_side_effect

        adapter = GeminiAdapter(api_key="test-key")
        result = adapter.list_models()

        ids = [m["id"] for m in result]
        assert "gemini-1.5-flash" in ids
        assert "gemini-2.5-flash" not in ids
        assert "text-embedding-004" not in ids

    def test_list_models_without_probe_returns_candidates_fast(self):
        from src.infrastructure.llm.gemini_adapter import GeminiAdapter

        m_active = MagicMock()
        m_active.name = "models/gemini-1.5-flash"
        m_active.display_name = "Gemini 1.5 Flash"
        m_active.supported_generation_methods = ["generateContent"]

        self._mock_genai.Client.return_value.models.list.return_value = [m_active]
        self._mock_genai.Client.return_value.models.count_tokens.reset_mock()

        adapter = GeminiAdapter(api_key="test-key")
        result = adapter.list_models(probe=False)

        assert len(result) == 1
        assert result[0]["id"] == "gemini-1.5-flash"
        self._mock_genai.Client.return_value.models.count_tokens.assert_not_called()




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

    def test_list_models_probes_with_one_token_and_filters_unusable(self):
        from src.infrastructure.llm.openai_adapter import OpenAIAdapter

        m_active = MagicMock()
        m_active.id = "gpt-4o"

        m_deprecated = MagicMock()
        m_deprecated.id = "gpt-old-unusable"

        m_audio = MagicMock()
        m_audio.id = "whisper-1"

        self._mock_openai.OpenAI.return_value.models.list.return_value.data = [
            m_active,
            m_deprecated,
            m_audio,
        ]

        def _create_side_effect(**kwargs):
            if kwargs.get("model") == "gpt-old-unusable":
                raise RuntimeError("Model decommissioned")
            resp = MagicMock()
            resp.choices = [MagicMock(message=MagicMock(content="ok"))]
            return resp

        self._mock_openai.OpenAI.return_value.chat.completions.create.side_effect = _create_side_effect

        adapter = OpenAIAdapter(api_key="test-key")
        result = adapter.list_models()

        ids = [m["id"] for m in result]
        assert "gpt-4o" in ids
        assert "gpt-old-unusable" not in ids
        assert "whisper-1" not in ids

    def test_list_models_without_probe_returns_candidates_fast(self):
        from src.infrastructure.llm.openai_adapter import OpenAIAdapter

        m_active = MagicMock()
        m_active.id = "gpt-4o"
        self._mock_openai.OpenAI.return_value.models.list.return_value.data = [m_active]
        self._mock_openai.OpenAI.return_value.chat.completions.create.reset_mock()

        adapter = OpenAIAdapter(api_key="test-key")
        result = adapter.list_models(probe=False)

        assert len(result) == 1
        assert result[0]["id"] == "gpt-4o"
        self._mock_openai.OpenAI.return_value.chat.completions.create.assert_not_called()

    def test_concurrent_complete_isolates_usage_without_shared_state(self):
        from concurrent.futures import ThreadPoolExecutor
        import threading
        from src.infrastructure.llm.openai_adapter import OpenAIAdapter

        barrier = threading.Barrier(2, timeout=2.0)

        def _create_side_effect(model, messages):
            prompt = messages[0]["content"]
            resp = MagicMock()
            if prompt == "p1":
                resp.choices = [MagicMock(message=MagicMock(content="c1"))]
                resp.usage = MagicMock(prompt_tokens=11, completion_tokens=22, total_tokens=33)
            else:
                resp.choices = [MagicMock(message=MagicMock(content="c2"))]
                resp.usage = MagicMock(prompt_tokens=77, completion_tokens=88, total_tokens=165)
            barrier.wait()
            return resp

        self._mock_openai.OpenAI.return_value.chat.completions.create.side_effect = _create_side_effect
        adapter = OpenAIAdapter(api_key="test-key")

        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(adapter.complete_with_usage, "p1", "gpt-4o")
            f2 = pool.submit(adapter.complete_with_usage, "p2", "gpt-4o")
            r1 = f1.result(timeout=3.0)
            r2 = f2.result(timeout=3.0)

        assert r1.content == "c1"
        assert r1.usage == {"input": 11, "output": 22, "total": 33}
        assert r2.content == "c2"
        assert r2.usage == {"input": 77, "output": 88, "total": 165}
        assert not hasattr(adapter, "_last_usage")




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

    def test_complete_image_returns_string(self, tmp_path: Path):
        from src.infrastructure.llm.anthropic_adapter import AnthropicAdapter

        img_file = tmp_path / "test.png"
        img_file.write_bytes(b"\x89PNG\r\n\x1a\n")

        adapter = AnthropicAdapter(api_key="test-key")
        result = adapter.complete_image("Describe diagram", img_file, "claude-3-5-sonnet-latest")

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

    def test_list_models_probes_with_count_tokens_and_filters_unusable(self):
        from src.infrastructure.llm.anthropic_adapter import AnthropicAdapter

        m_active = MagicMock()
        m_active.id = "claude-3-5-sonnet-latest"
        m_active.display_name = "Claude 3.5 Sonnet"

        m_unusable = MagicMock()
        m_unusable.id = "claude-unusable"
        m_unusable.display_name = "Claude Unusable"

        self._mock_anthropic.Anthropic.return_value.models.list.return_value = [
            m_active,
            m_unusable,
        ]

        def _count_tokens_side_effect(model, messages):
            if model == "claude-unusable":
                raise RuntimeError("Model access denied")
            return MagicMock(input_tokens=1)

        self._mock_anthropic.Anthropic.return_value.messages.count_tokens.side_effect = _count_tokens_side_effect

        adapter = AnthropicAdapter(api_key="test-key")
        result = adapter.list_models()

        ids = [m["id"] for m in result]
        assert "claude-3-5-sonnet-latest" in ids
        assert "claude-unusable" not in ids

    def test_list_models_without_probe_returns_candidates_fast(self):
        from src.infrastructure.llm.anthropic_adapter import AnthropicAdapter

        m_active = MagicMock()
        m_active.id = "claude-3-5-sonnet-latest"
        m_active.display_name = "Claude 3.5 Sonnet"

        self._mock_anthropic.Anthropic.return_value.models.list.return_value = [m_active]
        self._mock_anthropic.Anthropic.return_value.messages.count_tokens.reset_mock()

        adapter = AnthropicAdapter(api_key="test-key")
        result = adapter.list_models(probe=False)

        assert len(result) == 1
        assert result[0]["id"] == "claude-3-5-sonnet-latest"
        self._mock_anthropic.Anthropic.return_value.messages.count_tokens.assert_not_called()

    def test_complete_stream_yields_chunks_and_records_usage(self):
        from src.infrastructure.llm.anthropic_adapter import AnthropicAdapter

        stream_ctx = MagicMock()
        stream_ctx.text_stream = iter(["Hello ", "", "Claude!"])
        stream_ctx.get_final_message.return_value = MagicMock(
            usage=MagicMock(input_tokens=42, output_tokens=18)
        )
        stream_cm = MagicMock()
        stream_cm.__enter__.return_value = stream_ctx
        stream_cm.__exit__.return_value = False
        self._mock_anthropic.Anthropic.return_value.messages.stream.return_value = stream_cm

        adapter = AnthropicAdapter(api_key="test-key")
        chunks = list(adapter.complete_stream("Say hi", "claude-3-5-sonnet-latest"))

        assert chunks == ["Hello ", "Claude!"]
        assert adapter.get_last_usage() == {"input": 42, "output": 18, "total": 60}
        assert not hasattr(adapter, "_last_usage")

    def test_complete_stream_wraps_sdk_exception_as_llm_provider_error(self):
        from src.infrastructure.llm.anthropic_adapter import AnthropicAdapter

        self._mock_anthropic.Anthropic.return_value.messages.stream.side_effect = RuntimeError("stream boom")
        adapter = AnthropicAdapter(api_key="test-key")

        with pytest.raises(LLMProviderError, match="Anthropic streaming error: stream boom"):
            list(adapter.complete_stream("Say hi", "claude-3-5-sonnet-latest"))

    def test_adapters_extract_native_cached_token_counts(self, monkeypatch):
        from src.infrastructure.llm.anthropic_adapter import AnthropicAdapter
        from src.infrastructure.llm.gemini_adapter import GeminiAdapter
        from src.infrastructure.llm.openai_adapter import OpenAIAdapter

        # 1. Gemini: usage_metadata.cached_content_token_count
        g_mock = _make_genai_mock()
        monkeypatch.setitem(sys.modules, "google", MagicMock(genai=g_mock))
        monkeypatch.setitem(sys.modules, "google.genai", g_mock)
        gemini_resp = MagicMock()
        gemini_resp.text = "Cached Gemini reply"
        gemini_resp.usage_metadata = MagicMock(
            prompt_token_count=200,
            candidates_token_count=40,
            total_token_count=240,
            cached_content_token_count=120,
        )
        g_mock.Client.return_value.models.generate_content.return_value = gemini_resp
        g_adapter = GeminiAdapter(api_key="test-key")
        g_comp = g_adapter.complete_with_usage("Hello", "gemini-2.5-flash")
        assert g_comp.usage == {"input": 200, "output": 40, "total": 240, "cached": 120}

        # 2. OpenAI: usage.prompt_tokens_details.cached_tokens
        o_mock = _make_openai_mock()
        monkeypatch.setitem(sys.modules, "openai", o_mock)
        oai_resp = MagicMock()
        oai_resp.choices = [MagicMock(message=MagicMock(content="Cached OpenAI reply"))]
        oai_resp.usage = MagicMock(
            prompt_tokens=300,
            completion_tokens=50,
            total_tokens=350,
            prompt_tokens_details=MagicMock(cached_tokens=180),
        )
        o_mock.OpenAI.return_value.chat.completions.create.return_value = oai_resp
        o_adapter = OpenAIAdapter(api_key="test-key")
        o_comp = o_adapter.complete_with_usage("Hello", "gpt-4o")
        assert o_comp.usage == {"input": 300, "output": 50, "total": 350, "cached": 180}

        # 3. Anthropic: usage.cache_read_input_tokens
        anth_msg = MagicMock()
        text_block = MagicMock()
        text_block.text = "Cached Claude reply"
        anth_msg.content = [text_block]
        anth_msg.usage = MagicMock(
            input_tokens=150,
            output_tokens=30,
            cache_read_input_tokens=90,
        )
        self._mock_anthropic.Anthropic.return_value.messages.create.return_value = anth_msg
        a_adapter = AnthropicAdapter(api_key="test-key")
        a_comp = a_adapter.complete_with_usage("Hello", "claude-3-5-sonnet-latest")
        assert a_comp.usage == {"input": 150, "output": 30, "total": 180, "cached": 90}



