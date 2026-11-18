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
from collections.abc import Iterator

from src.domain.exceptions import LLMProviderError
from src.domain.ports.llm_provider import ILLMProvider, LLMCompletion
from src.infrastructure.llm.usage_tracking import UsageTrackingMixin, build_usage

_DEFAULT_MAX_TOKENS = 4096


class AnthropicAdapter(UsageTrackingMixin, ILLMProvider):
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

    def complete_with_usage(self, prompt: str, model_name: str) -> LLMCompletion:
        try:
            message = self._client.messages.create(
                model=model_name,
                max_tokens=_DEFAULT_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            usage: dict[str, int] = {}
            msg_usage = getattr(message, "usage", None)
            if msg_usage:
                usage = build_usage(
                    getattr(msg_usage, "input_tokens", 0),
                    getattr(msg_usage, "output_tokens", 0),
                )
            self._set_scoped_usage(usage)

            text = ""
            for block in message.content:
                block_text = getattr(block, "text", None)
                if isinstance(block_text, str):
                    text = block_text
                    break
            return LLMCompletion(content=text, usage=usage)
        except Exception as exc:  # noqa: BLE001
            raise LLMProviderError(str(exc)) from exc

    def complete(self, prompt: str, model_name: str) -> str:
        return self.complete_with_usage(prompt, model_name).content

    def complete_stream(self, prompt: str, model_name: str) -> Iterator[str]:
        try:
            with self._client.messages.stream(
                model=model_name,
                max_tokens=_DEFAULT_MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            ) as stream:
                for text in stream.text_stream:
                    if text:
                        yield text
                final_msg = stream.get_final_message() if hasattr(stream, "get_final_message") else None
                usage_obj = getattr(final_msg, "usage", None) if final_msg is not None else None
                if usage_obj:
                    self._set_scoped_usage(
                        build_usage(
                            getattr(usage_obj, "input_tokens", 0),
                            getattr(usage_obj, "output_tokens", 0),
                        )
                    )
                else:
                    self._set_scoped_usage({})
        except Exception as exc:  # noqa: BLE001
            raise LLMProviderError(f"Anthropic streaming error: {exc}") from exc


    @staticmethod
    def _fallback_candidates() -> list[tuple[str, str]]:
        return [
            ("claude-3-7-sonnet-latest", "Claude 3.7 Sonnet"),
            ("claude-3-5-sonnet-latest", "Claude 3.5 Sonnet"),
            ("claude-3-5-haiku-latest", "Claude 3.5 Haiku"),
            ("claude-3-opus-latest", "Claude 3 Opus"),
            ("claude-3-haiku-20240307", "Claude 3 Haiku"),
        ]

    def _fetch_candidates(self) -> list[tuple[str, str]]:
        if not (hasattr(self._client, "models") and hasattr(self._client.models, "list")):
            return self._fallback_candidates()
        try:
            candidates: list[tuple[str, str]] = []
            for m in self._client.models.list():
                m_id = getattr(m, "id", "")
                disp_name = getattr(m, "display_name", m_id) or m_id
                if m_id:
                    candidates.append((m_id, disp_name))
            return candidates or self._fallback_candidates()
        except Exception:
            return self._fallback_candidates()

    def _probe_model(self, model_id: str) -> bool:
        """Zero-cost lightweight probe: count_tokens validates model is accessible."""
        try:
            self._client.messages.count_tokens(
                model=model_id,
                messages=[{"role": "user", "content": "ping"}],
            )
            return True
        except Exception:
            return False

    def list_models(self, probe: bool = True) -> list[dict[str, str]]:
        try:
            candidates = self._fetch_candidates()
            result: list[dict[str, str]] = []
            for model_id, display_name in candidates:
                if probe and not self._probe_model(model_id):
                    continue
                result.append({"id": model_id, "name": display_name})
            return result
        except Exception as exc:
            raise LLMProviderError(str(exc)) from exc
