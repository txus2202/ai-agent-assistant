"""
Domain Port: ILLMProvider

Abstract interface that decouples the Application layer from any specific
LLM SDK. Every Infrastructure adapter (GeminiAdapter, OpenAIAdapter, etc.)
must implement this contract (ADR-004, ADR-010).
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class ILLMProvider(ABC):
    """
    Port (output) for LLM text completion.

    Concrete adapters must:
    - Implement ``complete()`` and return a non-empty string.
    - Catch all SDK-specific exceptions and re-raise them as
      ``src.domain.exceptions.LLMProviderError``.
    """

    @abstractmethod
    def complete(self, prompt: str, model_name: str) -> str:
        """
        Send ``prompt`` to the LLM and return its textual response.

        Args:
            prompt: The instruction or question to send. Non-empty.
            model_name: Free-form model identifier chosen by the user
                        (e.g. ``"gpt-4o"``, ``"gemini-1.5-pro"``).

        Returns:
            Non-empty string with the model's response.

        Raises:
            LLMProviderError: On any provider-level failure.
        """

    @abstractmethod
    def list_models(self) -> list[dict[str, str]]:
        """
        List all available models for this provider.

        Returns:
            A list of dictionaries, each containing 'id' and 'name' keys.
            Example: [{"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro"}]

        Raises:
            LLMProviderError: On any provider-level failure.
        """
