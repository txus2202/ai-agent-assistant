"""
Infrastructure Service: ImageGenerationService

Coordinates image generation via:
1. Google Imagen 3 (via google-genai SDK, enterprise grade and private)

Configured via environment variable:
IMAGE_GENERATION_PROVIDER: "imagen" | "" / "none"
"""
from __future__ import annotations

import asyncio
import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import ClassVar


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


class ImageGenerationService:
    """Service to generate and serve images based on active provider."""

    STORAGE_DIR: ClassVar[Path] = Path(tempfile.gettempdir()) / "atenea_images"

    @classmethod
    def get_provider_name(cls) -> str | None:
        """
        Return the normalized active image generation provider name, or None if disabled.
        Checks explicit OS environment variable first, then pydantic Settings (which loads .env).
        """
        # Explicit process environment variable has highest precedence
        env_val = os.getenv("IMAGE_GENERATION_PROVIDER")
        if env_val is None:
            env_val = os.getenv("IMAGE_PROVIDER")

        if env_val is not None:
            raw = env_val
        else:
            # Fallback to pydantic Settings (which loads .env file) only if env is unset
            try:
                from src.presentation.api.config import get_settings
                raw = get_settings().image_generation_provider
            except Exception:
                raw = ""

        val = str(raw).strip().lower()

        if val in ("imagen", "google", "imagen3", "imagen-3", "imagen-3.0"):
            return "imagen"
        return None

    @classmethod
    def is_enabled(cls) -> bool:
        """Return True if an image generation provider is actively configured."""
        return cls.get_provider_name() is not None

    @classmethod
    def generate_bytes(cls, prompt: str, provider: str | None = None) -> bytes:
        """Synchronously generate image bytes using the specified or active provider."""
        prov = provider or cls.get_provider_name()
        if not prov:
            raise ValueError(
                "No image generation provider configured. Set IMAGE_GENERATION_PROVIDER to 'imagen'."
            )

        if prov == "imagen":
            return ImagenGenerator.generate(prompt)
        else:
            raise ValueError(f"Unknown image generation provider: {prov}")

    @classmethod
    async def generate_and_save(cls, prompt: str, provider: str | None = None) -> tuple[str, str]:
        """
        Generate image asynchronously in a thread pool, save it to disk, and return (filename, web_url).
        """
        cls.STORAGE_DIR.mkdir(parents=True, exist_ok=True)

        image_bytes = await asyncio.to_thread(cls.generate_bytes, prompt, provider)

        filename = f"fidias_{uuid.uuid4().hex[:10]}.png"
        file_path = cls.STORAGE_DIR / filename
        await asyncio.to_thread(file_path.write_bytes, image_bytes)

        web_url = f"/api/images/{filename}"
        return filename, web_url

    @classmethod
    def get_image_path(cls, filename: str) -> Path | None:
        """
        Resolve and validate the path to an image file.
        Returns Path if exists and is safe, else None.
        """
        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", filename):
            return None

        file_path = (cls.STORAGE_DIR / filename).resolve()
        # Prevent directory traversal: must start with STORAGE_DIR
        storage_resolved = cls.STORAGE_DIR.resolve()
        try:
            file_path.relative_to(storage_resolved)
        except ValueError:
            return None

        return file_path if file_path.is_file() else None

