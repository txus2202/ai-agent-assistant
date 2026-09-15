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

from src.domain.exceptions import LLMProviderError
from src.domain.ports.llm_provider import ILLMProvider


class GeminiAdapter(ILLMProvider):
    """ILLMProvider backed by google-generativeai (Gemini)."""

    def __init__(self, api_key: str | None = None) -> None:
        try:
            import google.generativeai as _genai  # noqa: PLC0415 — intentional lazy import
        except ImportError as exc:
            raise LLMProviderError(
                "google-generativeai package is not installed. "
                "Run: pip install google-generativeai"
            ) from exc

        key = api_key or os.getenv("GEMINI_API_KEY")
        if not key:
            raise LLMProviderError(
                "GEMINI_API_KEY environment variable is not set. "
                "Set it in your .env file or pass api_key= explicitly."
            )

        _genai.configure(api_key=key)
        self._genai = _genai

    def complete(self, prompt: str, model_name: str) -> str:
        try:
            model = self._genai.GenerativeModel(model_name=model_name)
            response = model.generate_content(prompt)
            return response.text
        except Exception as exc:  # noqa: BLE001
            raise LLMProviderError(str(exc)) from exc
