"""
Infrastructure Adapter: OpenAIAdapter

Implements ILLMProvider using the openai SDK.
SDK is imported lazily in __init__.

API key resolution order:
  1. api_key parameter passed to __init__
  2. OPENAI_API_KEY environment variable
"""
from __future__ import annotations

import os

from src.domain.exceptions import LLMProviderError
from src.infrastructure.llm.base_openai_adapter import BaseOpenAIAdapter


class OpenAIAdapter(BaseOpenAIAdapter):
    """ILLMProvider backed by openai (GPT models)."""

    _provider_name = "OpenAI"

    def __init__(self, api_key: str | None = None) -> None:
        try:
            import openai as _openai  # noqa: PLC0415
        except ImportError as exc:
            raise LLMProviderError(
                "openai package is not installed. Run: pip install openai"
            ) from exc

        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise LLMProviderError(
                "OPENAI_API_KEY environment variable is not set. "
                "Set it in your .env file or pass api_key= explicitly."
            )

        self._client = _openai.OpenAI(api_key=key)

    @staticmethod
    def _is_chat_candidate(name_id: str) -> bool:
        if not name_id.startswith(("gpt", "o1", "o3", "chatgpt")):
            return False
        excluded_keywords = ("instruct", "vision", "audio", "realtime", "transcription", "tts")
        if any(x in name_id for x in excluded_keywords):
            return False
        if any(marker in name_id for marker in ("-0", "-1", "-20")):
            return False
        return True

    def _probe_model(self, name_id: str) -> bool:
        """1-token minimal probe: validates chat endpoint is accessible."""
        try:
            if name_id.startswith(("o1", "o3")):
                self._client.chat.completions.create(
                    model=name_id,
                    messages=[{"role": "user", "content": "ping"}],
                    max_completion_tokens=1,
                )
            else:
                self._client.chat.completions.create(
                    model=name_id,
                    messages=[{"role": "user", "content": "ping"}],
                    max_tokens=1,
                )
            return True
        except Exception:
            return False

    def list_models(self, probe: bool = True) -> list[dict[str, str]]:
        try:
            models = self._client.models.list()
            result: list[dict[str, str]] = []
            for m in models.data:
                name_id = m.id
                if not self._is_chat_candidate(name_id):
                    continue
                if probe and not self._probe_model(name_id):
                    continue
                result.append({"id": name_id, "name": name_id.upper()})
            return result
        except Exception as exc:
            raise LLMProviderError(str(exc)) from exc
