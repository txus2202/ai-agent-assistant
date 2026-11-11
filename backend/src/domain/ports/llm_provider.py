"""
Domain Port: ILLMProvider

Abstract interface that decouples the Application layer from any specific
LLM SDK. Every Infrastructure adapter (GeminiAdapter, OpenAIAdapter, etc.)
must implement this contract (ADR-004, ADR-010).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from pathlib import Path


class ILLMProvider(ABC):
    """
    Port (output) for LLM text completion.

    Concrete adapters must:
    - Implement ``complete()`` and return a non-empty string.
    - Catch all SDK-specific exceptions and re-raise them as
      ``src.domain.exceptions.LLMProviderError``.
    """

    def complete_image(self, prompt: str, image_path: Path, model_name: str) -> str:
        """
        Send ``prompt`` along with an image file to a multimodal LLM.

        Args:
            prompt: Text instruction or question about the image.
            image_path: Path to the local image file.
            model_name: Multimodal model identifier.

        Returns:
            Textual response describing or analyzing the image.

        Raises:
            LLMProviderError: On any provider-level failure or unsupported modal.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support image analysis.")

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

    def complete_stream(self, prompt: str, model_name: str) -> Iterator[str]:
        """
        Stream textual chunks from the LLM.
        Default fallback yields the single complete() response.
        """
        yield self.complete(prompt, model_name)

    @abstractmethod
    def list_models(self, probe: bool = True) -> list[dict[str, str]]:
        """
        List all available models for this provider.

        Args:
            probe: If True, executes healthcheck probing to filter out deprecated/unusable
                   models. If False, returns the raw candidate catalog without network probe delays.

        Returns:
            A list of dictionaries, each containing 'id' and 'name' keys.
            Example: [{"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro"}]

        Raises:
            LLMProviderError: On any provider-level failure.
        """
