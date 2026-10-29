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
from pathlib import Path

from src.domain.exceptions import LLMProviderError
from src.domain.ports.llm_provider import ILLMProvider


class OpenAIAdapter(ILLMProvider):
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

    def complete(self, prompt: str, model_name: str) -> str:
        try:
            response = self._client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
            )
            if hasattr(response, "usage") and response.usage:
                self._last_usage = {
                    "input": getattr(response.usage, "prompt_tokens", 0) or 0,
                    "output": getattr(response.usage, "completion_tokens", 0) or 0,
                    "total": getattr(response.usage, "total_tokens", 0) or 0,
                }
            else:
                self._last_usage = {}
            return response.choices[0].message.content or ""
        except Exception as exc:  # noqa: BLE001
            raise LLMProviderError(str(exc)) from exc

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

    def get_last_usage(self) -> dict[str, int]:
        """Return the token usage of the most recent complete() call."""
        return getattr(self, "_last_usage", {})


    def list_models(self) -> list[dict[str, str]]:
        try:
            models = self._client.models.list()
            result = []
            for m in models.data:
                name_id = m.id
                
                # Keep only gpt, o1, o3 models
                if not name_id.startswith(("gpt", "o1", "o3")):
                    continue
                    
                # Exclude deprecated or non-chat specialized models
                if "instruct" in name_id or "vision" in name_id or "audio" in name_id or "realtime" in name_id:
                    continue
                    
                # Exclude snapshot versions (which typically end in dates like -0613, -2024-05-13)
                # except we might want to keep some if they are the only ones, but standard aliases
                # like gpt-4o, gpt-4-turbo, o1-preview are always better to use.
                if "-0" in name_id or "-1" in name_id or "-2" in name_id:
                    continue
                    
                result.append({"id": name_id, "name": name_id.upper()})
                
            return result
        except Exception as exc:
            raise LLMProviderError(str(exc)) from exc
