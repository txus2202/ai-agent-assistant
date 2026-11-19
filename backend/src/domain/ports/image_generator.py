"""
Domain Port: IImageGenerator

Decouples Application agents and Presentation routes from concrete image generation adapters.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class IImageGenerator(Protocol):
    """Port for checking image generation configuration, creating images, and resolving stored files."""

    def get_provider_name(self) -> str | None:
        """Return the normalized active image generation provider name, or None when disabled."""
        ...

    def is_enabled(self) -> bool:
        """Return True when an image generation provider is configured."""
        ...

    async def generate_and_save(
        self,
        prompt: str,
        provider: str | None = None,
    ) -> tuple[str, str]:
        """Generate an image asynchronously, store it, and return ``(filename, web_url)``."""
        ...

    def get_image_path(self, filename: str) -> Path | None:
        """Resolve a previously saved image file path safely, or return None if invalid/missing."""
        ...

