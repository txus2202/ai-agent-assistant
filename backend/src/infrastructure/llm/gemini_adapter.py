"""
Infrastructure Adapter: GeminiAdapter

Implements ILLMProvider using the google-generativeai SDK.
SDK is imported lazily in __init__ to allow mocking in tests
and to raise a clear error when the package is not installed.

API key resolution order:
  1. api_key parameter passed to __init__
  2. GEMINI_API_KEY environment variable

Raises LLMProviderError for:
  - Missing SDK (ImportError)
  - Missing API key
  - Any SDK-level failure during complete()
"""
from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from src.domain.exceptions import LLMProviderError
from src.domain.ports.llm_provider import ILLMProvider


class GeminiAdapter(ILLMProvider):
    """ILLMProvider backed by google-genai (Gemini)."""

    def __init__(self, api_key: str | None = None, project: str | None = None, location: str = "europe-west1") -> None:
        try:
            from google import genai as _genai  # noqa: PLC0415 — intentional lazy import
        except ImportError as exc:
            raise LLMProviderError(
                "google-genai package is not installed. "
                "Run: pip install google-genai"
            ) from exc

        if project:
            # Requires Application Default Credentials (gcloud auth application-default login)
            self._client = _genai.Client(vertexai=True, project=project, location=location)
        else:
            # Fallback to AI Studio (API Key or Gemini CLI OAuth)
            key = api_key or os.getenv("GEMINI_API_KEY")
            if key:
                self._client = _genai.Client(api_key=key)
            else:
                try:
                    # Let the SDK try to find ADC (e.g., from Gemini CLI or gcloud)
                    self._client = _genai.Client()
                except Exception as exc:
                    raise LLMProviderError(
                        "No auth configured. Set GEMINI_API_KEY, GOOGLE_CLOUD_PROJECT, "
                        "or authenticate using the Gemini CLI."
                    ) from exc

    def complete(self, prompt: str, model_name: str) -> str:
        clean_model = model_name.strip().lower().replace(" ", "-")
        try:
            # Gemini Context Caching requires >= 32768 tokens.
            # We count tokens first to decide whether to cache.
            token_count_resp = self._client.models.count_tokens(
                model=clean_model,
                contents=prompt,
            )
            
            total_toks = getattr(token_count_resp, "total_tokens", None)
            if total_toks is not None and total_toks >= 32768:
                # Use explicit context caching
                cache = self._client.caches.create(
                    model=clean_model,
                    config={
                        'contents': [prompt],
                        'ttl': '3600s',  # 1 hour
                    },
                )
                response = self._client.models.generate_content(
                    model=clean_model,
                    contents="", # The prompt is entirely in the cache
                    config={'cached_content': cache.name}
                )
                # Cleanup cache after use to save costs (since this is per-agent specific)
                if getattr(cache, "name", None):
                    self._client.caches.delete(name=str(cache.name))
            else:
                # Normal request for smaller contexts
                response = self._client.models.generate_content(
                    model=clean_model,
                    contents=prompt,
                )

            if hasattr(response, "usage_metadata") and response.usage_metadata:
                self._last_usage = {
                    "input": getattr(response.usage_metadata, "prompt_token_count", 0) or 0,
                    "output": getattr(response.usage_metadata, "candidates_token_count", 0) or 0,
                    "total": getattr(response.usage_metadata, "total_token_count", 0) or 0,
                }
            else:
                self._last_usage = {}

            return getattr(response, "text", "") or ""

        except Exception as exc:  # noqa: BLE001
            raise LLMProviderError(str(exc)) from exc

    def complete_stream(self, prompt: str, model_name: str) -> Iterator[str]:
        clean_model = model_name.strip().lower().replace(" ", "-")
        try:
            response = self._client.models.generate_content_stream(
                model=clean_model,
                contents=prompt,
            )
            for chunk in response:
                text = getattr(chunk, "text", "")
                if text:
                    yield text
        except Exception as exc:  # noqa: BLE001
            raise LLMProviderError(f"Gemini streaming error: {exc}") from exc

    def complete_image(self, prompt: str, image_path: Path, model_name: str) -> str:
        """
        Send prompt along with an image to Gemini using google-genai multimodal capabilities.
        """
        clean_model = model_name.strip().lower().replace(" ", "-")
        try:
            import mimetypes  # noqa: PLC0415
            from google.genai import types  # noqa: PLC0415

            mime_type = mimetypes.guess_type(str(image_path))[0] or "image/jpeg"
            image_bytes = image_path.read_bytes()
            part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

            response = self._client.models.generate_content(
                model=clean_model,
                contents=[prompt, part],
            )
            return getattr(response, "text", "") or ""
        except Exception as exc:  # noqa: BLE001
            raise LLMProviderError(str(exc)) from exc

    def get_last_usage(self) -> dict[str, int]:
        """Return the token usage of the most recent complete() call."""
        return getattr(self, "_last_usage", {})


    def list_models(self) -> list[dict[str, str]]:
        try:
            models = self._client.models.list()
            result = []
            for m in models:
                # Filter for models that support text generation
                methods = getattr(m, "supported_generation_methods", [])
                if "generateContent" in methods or not methods:
                    raw_name = getattr(m, "name", None)
                    name_id = str(raw_name).replace("models/", "") if raw_name else str(m)
                    
                    # Exclude deprecated, vision-specific (old), and snapshot versions
                    if "vision" in name_id.lower() or "1.0" in name_id or "-00" in name_id:
                        continue
                        
                    display_name = getattr(m, "display_name", name_id)
                    result.append({"id": name_id, "name": display_name})
            return result
        except Exception as exc:
            raise LLMProviderError(str(exc)) from exc
