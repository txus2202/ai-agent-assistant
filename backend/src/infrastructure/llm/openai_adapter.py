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
from collections.abc import Iterator
from pathlib import Path

from src.domain.exceptions import LLMProviderError
from src.domain.ports.llm_provider import ILLMProvider, LLMCompletion
from src.infrastructure.llm.usage_tracking import UsageTrackingMixin, build_usage


class OpenAIAdapter(UsageTrackingMixin, ILLMProvider):
    """ILLMProvider backed by openai (GPT models)."""

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

    def complete_with_usage(self, prompt: str, model_name: str) -> LLMCompletion:
        try:
            response = self._client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
            )
            usage: dict[str, int] = {}
            resp_usage = getattr(response, "usage", None)
            if resp_usage:
                usage = build_usage(
                    getattr(resp_usage, "prompt_tokens", 0),
                    getattr(resp_usage, "completion_tokens", 0),
                    getattr(resp_usage, "total_tokens", None),
                )
            self._set_scoped_usage(usage)
            content = response.choices[0].message.content or ""
            return LLMCompletion(content=content, usage=usage)
        except Exception as exc:  # noqa: BLE001
            raise LLMProviderError(str(exc)) from exc

    def complete(self, prompt: str, model_name: str) -> str:
        return self.complete_with_usage(prompt, model_name).content

    def complete_stream(self, prompt: str, model_name: str) -> Iterator[str]:
        try:
            stream = self._client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                stream=True,
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as exc:  # noqa: BLE001
            raise LLMProviderError(f"OpenAI streaming error: {exc}") from exc

    def complete_image(self, prompt: str, image_path: Path, model_name: str) -> str:
        try:
            import base64  # noqa: PLC0415
            import mimetypes  # noqa: PLC0415

            mime_type = mimetypes.guess_type(str(image_path))[0] or "image/jpeg"
            b64_data = base64.b64encode(image_path.read_bytes()).decode("utf-8")
            data_url = f"data:{mime_type};base64,{b64_data}"

            response = self._client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    }
                ],
            )
            return response.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001
            raise LLMProviderError(str(exc)) from exc

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
