"""
Infrastructure Adapter: LocalLLMAdapter

Implements ILLMProvider for local AI servers (Ollama, LM Studio, vLLM, llama.cpp)
via their OpenAI-compatible `/v1` API.

Base URL resolution order:
  1. base_url parameter passed to __init__
  2. LOCAL_LLM_BASE_URL environment variable
  3. OLLAMA_BASE_URL environment variable

API key resolution order:
  1. api_key parameter passed to __init__
  2. LOCAL_LLM_API_KEY environment variable
  3. Defaults to "ollama" (local servers do not require a secret key, but the
     OpenAI client requires a non-empty string).
"""
from __future__ import annotations

import os

from src.domain.exceptions import LLMProviderError
from src.infrastructure.llm.base_openai_adapter import BaseOpenAIAdapter

_EMBEDDING_KEYWORDS: tuple[str, ...] = (
    "embed",
    "minilm",
    "bge-",
    "nomic-embed",
    "mxbai-embed",
    "snowflake-arctic-embed",
    "e5-",
)


def normalize_local_base_url(raw_url: str) -> str:
    """
    Normalize a local LLM server URL so it targets the OpenAI-compatible ``/v1`` endpoint.
    For example:
      - ``http://localhost:11434``    -> ``http://localhost:11434/v1``
      - ``http://localhost:11434/``   -> ``http://localhost:11434/v1``
      - ``http://localhost:11434/v1`` -> ``http://localhost:11434/v1``
    """
    cleaned = raw_url.strip().rstrip("/")
    if not cleaned:
        return ""
    if not cleaned.endswith("/v1"):
        return f"{cleaned}/v1"
    return cleaned


class LocalLLMAdapter(BaseOpenAIAdapter):
    """ILLMProvider backed by a local Ollama / OpenAI-compatible inference server."""

    _provider_name = "Local LLM"

    def __init__(self, base_url: str | None = None, api_key: str | None = None) -> None:
        try:
            import openai as _openai  # noqa: PLC0415
        except ImportError as exc:
            raise LLMProviderError(
                "openai package is not installed. Run: pip install openai"
            ) from exc

        raw_url = (
            base_url
            or os.getenv("LOCAL_LLM_BASE_URL")
            or os.getenv("OLLAMA_BASE_URL")
            or ""
        )
        normalized_url = normalize_local_base_url(raw_url)
        if not normalized_url:
            raise LLMProviderError(
                "LOCAL_LLM_BASE_URL environment variable is not set. "
                "Set it in your .env file (e.g. LOCAL_LLM_BASE_URL=http://localhost:11434) "
                "or pass base_url= explicitly."
            )

        resolved_key = (api_key or os.getenv("LOCAL_LLM_API_KEY") or "").strip() or "ollama"
        self.base_url = normalized_url
        self._client = _openai.OpenAI(base_url=self.base_url, api_key=resolved_key)

    @staticmethod
    def _is_chat_candidate(name_id: str) -> bool:
        lower = name_id.lower()
        return not any(keyword in lower for keyword in _EMBEDDING_KEYWORDS)

    def list_models(self, probe: bool = True) -> list[dict[str, str]]:  # noqa: ARG002
        """
        Return all non-embedding models available on the local Ollama server.

        Note: Does NOT execute a 1-token chat completion probe per model even when
        ``probe=True``, because forcing Ollama to load and unload every installed model
        in RAM/VRAM sequentially would thrash memory on local/homelab hardware.
        """
        try:
            models = self._client.models.list()
            result: list[dict[str, str]] = []
            for m in models.data:
                name_id = m.id
                if not self._is_chat_candidate(name_id):
                    continue
                result.append({"id": name_id, "name": name_id.upper()})
            return result
        except Exception as exc:  # noqa: BLE001
            raise LLMProviderError(str(exc)) from exc

