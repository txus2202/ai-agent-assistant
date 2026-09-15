"""
Infrastructure Adapter: AnthropicAdapter

Implements ILLMProvider using the anthropic SDK.
SDK is imported lazily in __init__.

API key resolution order:
  1. api_key parameter passed to __init__
  2. ANTHROPIC_API_KEY environment variable
"""
from __future__ import annotations

import os

from src.domain.exceptions import LLMProviderError
from src.domain.ports.llm_provider import ILLMProvider

_DEFAULT_MAX_TOKENS = 4096


class AnthropicAdapter(ILLMProvider):
    """ILLMProvider backed by anthropic (Claude models)."""

    def __init__(self, api_key: str | None = None) -> None:
        try:
            import anthropic as _anthropic  # noqa: PLC0415
        except ImportError as exc:
            raise LLMProviderError(
                "anthropic package is not installed. Run: pip install anthropic"
            ) from exc

        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise LLMProviderError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Set it in your .env file or pass api_key= explicitly."
            )

        self._client = _anthropic.Anthropic(api_key=key)

    def complete(self, prompt: str, model_name: str) -> str:
        try:
            message = self._client.messages.create(
                model=model_name,
                max_tokens=_DEFAULT_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except Exception as exc:  # noqa: BLE001
            raise LLMProviderError(str(exc)) from exc
