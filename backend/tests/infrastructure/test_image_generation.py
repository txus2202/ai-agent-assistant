"""
Unit tests for Image Generation Service and Providers (Imagen 3).
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.image_generation.service import (
    ImageGenerationService,
    ImagenGenerator,
)


class TestImageGenerationService:
    def test_provider_name_normalization(self, monkeypatch):
        from src.presentation.api import config
        mock_settings = MagicMock()
        mock_settings.image_generation_provider = ""
        monkeypatch.setattr(config, "get_settings", lambda: mock_settings)

        # Deprecated/removed providers should return None
        monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "pollinations")
        assert ImageGenerationService.get_provider_name() is None
        assert ImageGenerationService.is_enabled() is False

        monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "FLUX")
        assert ImageGenerationService.get_provider_name() is None

        # Imagen 3 variants
        monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "imagen")
        assert ImageGenerationService.get_provider_name() == "imagen"
        assert ImageGenerationService.is_enabled() is True

        monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "Google")
        assert ImageGenerationService.get_provider_name() == "imagen"

        monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "imagen-3.0")
        assert ImageGenerationService.get_provider_name() == "imagen"

        monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "none")
        assert ImageGenerationService.get_provider_name() is None
        assert ImageGenerationService.is_enabled() is False

        monkeypatch.delenv("IMAGE_GENERATION_PROVIDER", raising=False)
        monkeypatch.delenv("IMAGE_PROVIDER", raising=False)
        assert ImageGenerationService.get_provider_name() is None
        assert ImageGenerationService.is_enabled() is False

    def test_provider_name_from_settings(self, monkeypatch):
        from src.presentation.api import config
        monkeypatch.delenv("IMAGE_GENERATION_PROVIDER", raising=False)
        monkeypatch.delenv("IMAGE_PROVIDER", raising=False)

        mock_settings = MagicMock()
        mock_settings.image_generation_provider = "imagen"
        monkeypatch.setattr(config, "get_settings", lambda: mock_settings)
        assert ImageGenerationService.get_provider_name() == "imagen"
        assert ImageGenerationService.is_enabled() is True

    def test_generate_bytes_raises_when_disabled(self, monkeypatch):
        from src.presentation.api import config

        monkeypatch.delenv("IMAGE_GENERATION_PROVIDER", raising=False)
        monkeypatch.delenv("IMAGE_PROVIDER", raising=False)
        mock_settings = MagicMock()
        mock_settings.image_generation_provider = ""
        monkeypatch.setattr(config, "get_settings", lambda: mock_settings)

        with pytest.raises(ValueError, match="No image generation provider configured"):
            ImageGenerationService.generate_bytes("Cyberpunk dashboard")

    def test_imagen_generator_success(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "fake_key")

        mock_image = MagicMock()
        mock_image.image_bytes = b"\x89PNG\r\n\x1a\nimagenbytes"
        mock_generated = MagicMock()
        mock_generated.image = mock_image

        mock_result = MagicMock()
        mock_result.generated_images = [mock_generated]

        mock_client = MagicMock()
        mock_client.models.generate_images.return_value = mock_result

        with patch("google.genai.Client", return_value=mock_client):
            data = ImagenGenerator.generate("Architectural sketch")
            assert data == b"\x89PNG\r\n\x1a\nimagenbytes"
            mock_client.models.generate_images.assert_called_once()

    def test_imagen_generator_empty_prompt_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            ImagenGenerator.generate("   ")

    @pytest.mark.anyio
    async def test_generate_and_save_returns_url_and_persists_file(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ImageGenerationService, "STORAGE_DIR", tmp_path)
        monkeypatch.setattr(ImageGenerationService, "generate_bytes", lambda prompt, provider=None: b"fake_png_data")

        filename, url = await ImageGenerationService.generate_and_save("Test prompt", provider="imagen")

        assert filename.startswith("fidias_")
        assert filename.endswith(".png")
        assert url == f"/api/images/{filename}"

        saved_file = tmp_path / filename
        assert saved_file.is_file()
        assert saved_file.read_bytes() == b"fake_png_data"

        # Verify get_image_path resolves it
        resolved = ImageGenerationService.get_image_path(filename)
        assert resolved == saved_file

    def test_get_image_path_prevents_traversal(self, monkeypatch, tmp_path):
        monkeypatch.setattr(ImageGenerationService, "STORAGE_DIR", tmp_path)

        # Illegal filenames
        assert ImageGenerationService.get_image_path("../../../etc/passwd") is None
        assert ImageGenerationService.get_image_path("sub/folder/file.png") is None
        assert ImageGenerationService.get_image_path("nonexistent.png") is None

