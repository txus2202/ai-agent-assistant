"""
Infrastructure: Image Generation Package.

Provides connectors for image generation:
- Google Imagen 3 (via google-genai SDK, enterprise grade and private)
"""
from src.infrastructure.image_generation.service import ImageGenerationService

__all__ = ["ImageGenerationService"]

