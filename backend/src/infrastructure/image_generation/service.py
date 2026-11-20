"""
Infrastructure Service: ImageGenerationService

Coordinates image generation via:
1. Google Imagen 3 (via google-genai SDK, enterprise grade and private)

Configured via constructor injection from the composition root
(IMAGE_GENERATION_PROVIDER: "imagen" | "" / "none").
"""
from __future__ import annotations

import asyncio
import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import ClassVar

from src.domain.ports.image_generator import IImageGenerator


class ImagenGenerator:
    """Generates images using Google Imagen 3 via google-genai SDK."""

    MODEL_NAME: ClassVar[str] = "imagen-3.0-generate-002"

    @classmethod
    def generate(cls, prompt: str, api_key: str | None = None, project: str | None = None) -> bytes:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise RuntimeError(
                "google-genai package is not installed. Run: pip install google-genai"
            ) from exc

        clean_prompt = prompt.strip()
        if not clean_prompt:
            raise ValueError("Prompt cannot be empty for image generation")

        key = api_key or os.getenv("GEMINI_API_KEY")
        if project:
            client = genai.Client(vertexai=True, project=project)
        elif key:
            client = genai.Client(api_key=key)
        else:
            client = genai.Client()

        result = client.models.generate_images(
            model=cls.MODEL_NAME,
            prompt=clean_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                output_mime_type="image/png",
                aspect_ratio="1:1",
            ),
        )

        if not result.generated_images:
            raise RuntimeError("Imagen 3 returned no images")

        return result.generated_images[0].image.image_bytes


class ImageGenerationService(IImageGenerator):
    """Service to generate and serve images based on injected provider configuration."""

    STORAGE_DIR: ClassVar[Path] = Path(tempfile.gettempdir()) / "atenea_images"

    def __init__(
        self,
        provider_name: str | None = None,
        *,
        api_key: str | None = None,
        project: str | None = None,
        storage_dir: Path | None = None,
    ) -> None:
        self._provider_name = provider_name
        self._api_key = api_key
        self._project = project
        self._storage_dir = storage_dir

    def _effective_storage_dir(self) -> Path:
        return self._storage_dir if self._storage_dir is not None else type(self).STORAGE_DIR

    @staticmethod
    def normalize_provider_name(raw: str | None) -> str | None:
        """Normalize raw provider configuration to canonical provider id or None."""
        val = (raw or "").strip().lower()
        if val in ("imagen", "google", "imagen3", "imagen-3", "imagen-3.0"):
            return "imagen"
        return None

    def get_provider_name(self) -> str | None:
        """Return normalized active image generation provider name, or None if disabled."""
        if self._provider_name is not None:
            raw = self._provider_name
        else:
            env_val = os.getenv("IMAGE_GENERATION_PROVIDER")
            if env_val is None:
                env_val = os.getenv("IMAGE_PROVIDER")
            raw = env_val or ""
        return self.normalize_provider_name(raw)

    def is_enabled(self) -> bool:
        """Return True if an image generation provider is actively configured."""
        return self.get_provider_name() is not None

    def generate_bytes(self, prompt: str, provider: str | None = None) -> bytes:
        """Synchronously generate image bytes using the specified or active provider."""
        prov = self.normalize_provider_name(provider) if provider is not None else self.get_provider_name()
        if not prov:
            raise ValueError(
                "No image generation provider configured. Set IMAGE_GENERATION_PROVIDER to 'imagen'."
            )

        if prov == "imagen":
            return ImagenGenerator.generate(
                prompt,
                api_key=self._api_key,
                project=self._project,
            )
        raise ValueError(f"Unknown image generation provider: {prov}")

    async def generate_and_save(self, prompt: str, provider: str | None = None) -> tuple[str, str]:
        """Generate image asynchronously in a thread pool, save it to disk, and return (filename, web_url)."""
        storage_dir = self._effective_storage_dir()
        storage_dir.mkdir(parents=True, exist_ok=True)

        image_bytes = await asyncio.to_thread(self.generate_bytes, prompt, provider)

        filename = f"fidias_{uuid.uuid4().hex[:10]}.png"
        file_path = storage_dir / filename
        await asyncio.to_thread(file_path.write_bytes, image_bytes)

        web_url = f"/api/images/{filename}"
        return filename, web_url

    def get_image_path(self, filename: str) -> Path | None:
        """Resolve and validate the path to an image file safely, preventing path traversal."""
        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", filename):
            return None

        storage_dir = self._effective_storage_dir()
        file_path = (storage_dir / filename).resolve()
        storage_resolved = storage_dir.resolve()
        try:
            file_path.relative_to(storage_resolved)
        except ValueError:
            return None

        return file_path if file_path.is_file() else None
