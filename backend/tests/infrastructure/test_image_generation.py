"""
Unit tests for Image Generation Service and Providers (Imagen 3).
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.domain.ports.image_generator import IImageGenerator
from src.infrastructure.image_generation.service import (
    ImageGenerationService,
    ImagenGenerator,
)


class TestImageGenerationService:
    def test_implements_image_generator_port(self):
        service = ImageGenerationService(provider_name="imagen")
        assert isinstance(service, IImageGenerator)

    def test_provider_name_normalization_from_env_when_unconfigured(self, monkeypatch):
        monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "pollinations")
        svc = ImageGenerationService()
        assert svc.get_provider_name() is None
        assert svc.is_enabled() is False

        monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "FLUX")
        assert svc.get_provider_name() is None

        monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "imagen")
        assert svc.get_provider_name() == "imagen"
        assert svc.is_enabled() is True

        monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "Google")
        assert svc.get_provider_name() == "imagen"

        monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "imagen-3.0")
        assert svc.get_provider_name() == "imagen"

        monkeypatch.setenv("IMAGE_GENERATION_PROVIDER", "none")
        assert svc.get_provider_name() is None
        assert svc.is_enabled() is False

        monkeypatch.delenv("IMAGE_GENERATION_PROVIDER", raising=False)
        monkeypatch.delenv("IMAGE_PROVIDER", raising=False)
        assert svc.get_provider_name() is None
        assert svc.is_enabled() is False

    def test_provider_name_from_injected_config(self, monkeypatch):
        monkeypatch.delenv("IMAGE_GENERATION_PROVIDER", raising=False)
        monkeypatch.delenv("IMAGE_PROVIDER", raising=False)

        svc = ImageGenerationService(provider_name="imagen")
        assert svc.get_provider_name() == "imagen"
        assert svc.is_enabled() is True

        disabled_svc = ImageGenerationService(provider_name="")
        assert disabled_svc.get_provider_name() is None
        assert disabled_svc.is_enabled() is False

    def test_generate_bytes_raises_when_disabled(self, monkeypatch):
        monkeypatch.delenv("IMAGE_GENERATION_PROVIDER", raising=False)
        monkeypatch.delenv("IMAGE_PROVIDER", raising=False)

        svc = ImageGenerationService(provider_name="")
        with pytest.raises(ValueError, match="No image generation provider configured"):
            svc.generate_bytes("Cyberpunk dashboard")

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

    def test_generate_bytes_forwards_injected_credentials(self):
        mock_image = MagicMock()
        mock_image.image_bytes = b"png_bytes"
        mock_generated = MagicMock()
        mock_generated.image = mock_image
        mock_result = MagicMock()
        mock_result.generated_images = [mock_generated]
        mock_client = MagicMock()
        mock_client.models.generate_images.return_value = mock_result

        svc = ImageGenerationService(provider_name="imagen", api_key="injected-gemini-key")
        with patch("google.genai.Client", return_value=mock_client) as client_cls:
            data = svc.generate_bytes("Cloud diagram")
            assert data == b"png_bytes"
            client_cls.assert_called_once_with(api_key="injected-gemini-key")

    def test_imagen_generator_empty_prompt_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            ImagenGenerator.generate("   ")

    @pytest.mark.anyio
    async def test_generate_and_save_returns_url_and_persists_file(self, monkeypatch, tmp_path):
        svc = ImageGenerationService(provider_name="imagen", storage_dir=tmp_path)
        monkeypatch.setattr(svc, "generate_bytes", lambda prompt, provider=None: b"fake_png_data")

        filename, url = await svc.generate_and_save("Test prompt", provider="imagen")

        assert filename.startswith("fidias_")
        assert filename.endswith(".png")
        assert url == f"/api/images/{filename}"

        saved_file = tmp_path / filename
        assert saved_file.is_file()
        assert saved_file.read_bytes() == b"fake_png_data"

        resolved = svc.get_image_path(filename)
        assert resolved == saved_file

    def test_get_image_path_prevents_traversal(self, tmp_path):
        svc = ImageGenerationService(storage_dir=tmp_path)

        assert svc.get_image_path("../../../etc/passwd") is None
        assert svc.get_image_path("sub/folder/file.png") is None
        assert svc.get_image_path("nonexistent.png") is None

    def test_imagen_generator_developer_api_uses_generate_content_when_generate_images_unsupported(
        self, monkeypatch
    ):
        monkeypatch.setenv("GEMINI_API_KEY", "developer-api-key")

        mock_client = MagicMock()
        mock_client.models.generate_images.side_effect = ValueError(
            "This method is only supported in Gemini Enterprise Agent Platform mode, "
            "not in Gemini Developer API mode."
        )

        mock_part = MagicMock()
        mock_part.inline_data.data = b"\x89PNG\r\n\x1a\ngemini_image_bytes"
        mock_resp = MagicMock()
        mock_resp.parts = [mock_part]
        mock_resp.candidates = []
        mock_client.models.generate_content.return_value = mock_resp

        with patch("google.genai.Client", return_value=mock_client):
            data = ImagenGenerator.generate("Futuristic microservices dashboard")
            assert data == b"\x89PNG\r\n\x1a\ngemini_image_bytes"
            mock_client.models.generate_content.assert_called_once()

    def test_imagen_generator_falls_back_across_gemini_image_models(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "developer-api-key")
        monkeypatch.delenv("GEMINI_IMAGE_MODEL", raising=False)

        mock_client = MagicMock()
        mock_client.models.generate_images.side_effect = ValueError(
            "This method is only supported in Gemini Enterprise Agent Platform mode"
        )

        def _gen_content_side_effect(*, model, contents, config=None):
            if model == "gemini-3.1-flash-image":
                raise RuntimeError("404 model not found")
            part = MagicMock()
            part.inline_data.data = b"\x89PNG\r\n\x1a\nfallback_model_bytes"
            resp = MagicMock()
            resp.parts = [part]
            return resp

        mock_client.models.generate_content.side_effect = _gen_content_side_effect

        with patch("google.genai.Client", return_value=mock_client):
            data = ImagenGenerator.generate("Clean architecture diagram")
            assert data == b"\x89PNG\r\n\x1a\nfallback_model_bytes"
            assert mock_client.models.generate_content.call_count == 2

