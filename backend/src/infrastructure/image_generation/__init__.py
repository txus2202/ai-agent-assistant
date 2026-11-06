"""
Infrastructure: Image Generation Package.

Provides connectors for image generation:
- Pollinations (Flux model, free tier / public API)
- Google Imagen 3 (via google-genai SDK)
"""
from src.infrastructure.image_generation.service import ImageGenerationService

__all__ = ["ImageGenerationService"]

