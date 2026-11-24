"""
Infrastructure Base Adapter: BaseOpenAIAdapter

Common base implementation for OpenAI and OpenAI-compatible (LocalLLM/Ollama/vLLM) adapters.
Consolidates standard chat completions, streaming, token usage tracking, and vision/image completion.
"""
from __future__ import annotations

import base64
import mimetypes
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from src.domain.exceptions import LLMProviderError
from src.domain.ports.llm_provider import ILLMProvider, LLMCompletion
from src.infrastructure.llm.usage_tracking import UsageTrackingMixin, build_usage


class BaseOpenAIAdapter(UsageTrackingMixin, ILLMProvider):
    """Base class for ILLMProvider adapters backed by an OpenAI-compatible API client."""

    _client: Any
    _provider_name: str = "OpenAI"

    def complete_with_usage(self, prompt: str, model_name: str) -> LLMCompletion:
        try:
            response = self._client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
            )
            usage: dict[str, int] = {}
            resp_usage = getattr(response, "usage", None)
            if resp_usage:
                details = getattr(resp_usage, "prompt_tokens_details", None)
                cached = getattr(details, "cached_tokens", 0) if details is not None else 0
                usage = build_usage(
                    getattr(resp_usage, "prompt_tokens", 0),
                    getattr(resp_usage, "completion_tokens", 0),
                    getattr(resp_usage, "total_tokens", None),
                    cached,
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
            last_usage: dict[str, int] = {}
            for chunk in stream:
                resp_usage = getattr(chunk, "usage", None)
                if resp_usage:
                    details = getattr(resp_usage, "prompt_tokens_details", None)
                    cached = getattr(details, "cached_tokens", 0) if details is not None else 0
                    last_usage = build_usage(
                        getattr(resp_usage, "prompt_tokens", 0),
                        getattr(resp_usage, "completion_tokens", 0),
                        getattr(resp_usage, "total_tokens", None),
                        cached,
                    )
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
            self._set_scoped_usage(last_usage)
        except Exception as exc:  # noqa: BLE001
            raise LLMProviderError(f"{self._provider_name} streaming error: {exc}") from exc

    def complete_image(self, prompt: str, image_path: Path, model_name: str) -> str:
        try:
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

