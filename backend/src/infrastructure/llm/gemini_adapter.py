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
from typing import Any

from src.domain.exceptions import LLMProviderError
from src.domain.ports.llm_provider import ILLMProvider, LLMCompletion
from src.infrastructure.llm.usage_tracking import UsageTrackingMixin, build_usage


class GeminiAdapter(UsageTrackingMixin, ILLMProvider):
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

    def complete_with_usage(self, prompt: str, model_name: str) -> LLMCompletion:
        clean_model = model_name.strip().lower().replace(" ", "-")
        try:
            response = self._client.models.generate_content(
                model=clean_model,
                contents=prompt,
            )

            usage: dict[str, int] = {}
            usage_meta = getattr(response, "usage_metadata", None)
            if usage_meta:
                usage = build_usage(
                    getattr(usage_meta, "prompt_token_count", 0),
                    getattr(usage_meta, "candidates_token_count", 0),
                    getattr(usage_meta, "total_token_count", None),
                    getattr(usage_meta, "cached_content_token_count", 0),
                )
            self._set_scoped_usage(usage)

            text = getattr(response, "text", "") or ""
            return LLMCompletion(content=text, usage=usage)

        except Exception as exc:  # noqa: BLE001
            raise LLMProviderError(str(exc)) from exc

    def complete(self, prompt: str, model_name: str) -> str:
        return self.complete_with_usage(prompt, model_name).content

    def complete_stream(self, prompt: str, model_name: str) -> Iterator[str]:
        clean_model = model_name.strip().lower().replace(" ", "-")
        try:
            response = self._client.models.generate_content_stream(
                model=clean_model,
                contents=prompt,
            )
            last_usage: dict[str, int] = {}
            for chunk in response:
                usage_meta = getattr(chunk, "usage_metadata", None)
                if usage_meta:
                    last_usage = build_usage(
                        getattr(usage_meta, "prompt_token_count", 0),
                        getattr(usage_meta, "candidates_token_count", 0),
                        getattr(usage_meta, "total_token_count", None),
                        getattr(usage_meta, "cached_content_token_count", 0),
                    )
                text = getattr(chunk, "text", "")
                if text:
                    yield text
            self._set_scoped_usage(last_usage)
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

    @staticmethod
    def _supports_generation(model: Any) -> bool:
        methods = getattr(model, "supported_generation_methods", [])
        actions = getattr(model, "supported_actions", [])
        return (
            "generateContent" in methods
            or "generateContent" in actions
            or (not methods and not actions)
        )

    @staticmethod
    def _extract_model_identity(model: Any) -> tuple[str, str]:
        raw_name = getattr(model, "name", None)
        name_id = str(raw_name).replace("models/", "") if raw_name else str(model)
        display_name = getattr(model, "display_name", name_id) or name_id
        return name_id, display_name

    @staticmethod
    def _is_excluded(name_id: str) -> bool:
        lowered = name_id.lower()
        return "embedding" in lowered or "aqa" in lowered

    def _probe_model(self, name_id: str) -> bool:
        """Zero-cost lightweight probe: count_tokens validates model is currently active."""
        try:
            self._client.models.count_tokens(model=name_id, contents="ping")
            return True
        except Exception:
            return False

    def list_models(self, probe: bool = True) -> list[dict[str, str]]:
        try:
            models = self._client.models.list()
            result: list[dict[str, str]] = []
            for m in models:
                if not self._supports_generation(m):
                    continue
                name_id, display_name = self._extract_model_identity(m)
                if self._is_excluded(name_id):
                    continue
                if probe and not self._probe_model(name_id):
                    continue
                result.append({"id": name_id, "name": display_name})
            return result
        except Exception as exc:
            raise LLMProviderError(str(exc)) from exc
