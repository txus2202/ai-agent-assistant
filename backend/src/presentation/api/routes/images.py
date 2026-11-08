"""
Presentation: Route to serve generated images.

Endpoints:
- GET /images/{filename}
- GET /api/images/{filename}
"""
from __future__ import annotations

import mimetypes
import re

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.infrastructure.image_generation.service import ImageGenerationService

router = APIRouter(tags=["images"])

IMAGE_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"description": "Invalid filename format"},
    404: {"description": "Image not found"},
}


@router.get("/images/{filename}", responses=IMAGE_RESPONSES)
@router.get("/api/images/{filename}", responses=IMAGE_RESPONSES)
async def get_generated_image(filename: str):
    """Serve a generated image file safely."""
    if not re.match(r"^[a-zA-Z0-9_\-\.]+$", filename):
        raise HTTPException(status_code=400, detail="Invalid filename format")

    image_path = ImageGenerationService.get_image_path(filename)
    if not image_path or not image_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")

    mime_type, _ = mimetypes.guess_type(str(image_path))
    return FileResponse(image_path, media_type=mime_type or "image/png")

