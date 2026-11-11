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
            if hasattr(message, "usage") and message.usage:
                in_t = getattr(message.usage, "input_tokens", 0) or 0
                out_t = getattr(message.usage, "output_tokens", 0) or 0
                self._last_usage = {
                    "input": in_t,
                    "output": out_t,
                    "total": in_t + out_t,
                }
            else:
                self._last_usage = {}
            return message.content[0].text
        except Exception as exc:  # noqa: BLE001
            raise LLMProviderError(str(exc)) from exc

    def get_last_usage(self) -> dict[str, int]:
        """Return the token usage of the most recent complete() call."""
        return getattr(self, "_last_usage", {})


    def list_models(self, probe: bool = True) -> list[dict[str, str]]:
        try:
            candidates: list[tuple[str, str]] = []
            if hasattr(self._client, "models") and hasattr(self._client.models, "list"):
                try:
                    for m in self._client.models.list():
                        m_id = getattr(m, "id", "")
                        disp_name = getattr(m, "display_name", m_id) or m_id
                        if m_id:
                            candidates.append((m_id, disp_name))
                except Exception:
                    pass

            if not candidates:
                candidates = [
                    ("claude-3-7-sonnet-latest", "Claude 3.7 Sonnet"),
                    ("claude-3-5-sonnet-latest", "Claude 3.5 Sonnet"),
                    ("claude-3-5-haiku-latest", "Claude 3.5 Haiku"),
                    ("claude-3-opus-latest", "Claude 3 Opus"),
                    ("claude-3-haiku-20240307", "Claude 3 Haiku"),
                ]

            result: list[dict[str, str]] = []
            for model_id, display_name in candidates:
                if probe:
                    # Zero-cost lightweight probe: count_tokens validates model is accessible
                    try:
                        self._client.messages.count_tokens(
                            model=model_id,
                            messages=[{"role": "user", "content": "ping"}],
                        )
                    except Exception:
                        continue
                result.append({"id": model_id, "name": display_name})
            return result
        except Exception as exc:
            raise LLMProviderError(str(exc)) from exc
