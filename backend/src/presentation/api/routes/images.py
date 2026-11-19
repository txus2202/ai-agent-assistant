"""
Presentation: Route to serve generated images.

Endpoints:
- GET /images/{filename}
- GET /api/images/{filename}
"""
from __future__ import annotations

import mimetypes
import re

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from src.domain.entities.user import User
from src.domain.ports.image_generator import IImageGenerator
from src.presentation.api.dependencies.auth import get_current_user
from src.presentation.api.dependencies.llm import get_image_generator

router = APIRouter(tags=["images"])

IMAGE_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"description": "Invalid filename format"},
    404: {"description": "Image not found"},
}


@router.get("/images/{filename}", responses=IMAGE_RESPONSES)
async def get_generated_image(
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    image_generator: Annotated[IImageGenerator, Depends(get_image_generator)],
):
    """Serve a generated image file safely."""
    if not re.match(r"^[a-zA-Z0-9_\-\.]+$", filename):
        raise HTTPException(status_code=400, detail="Invalid filename format")

    image_path = image_generator.get_image_path(filename)
    if not image_path or not image_path.is_file():
        raise HTTPException(status_code=404, detail="Image not found")

    mime_type, _ = mimetypes.guess_type(str(image_path))
    return FileResponse(image_path, media_type=mime_type or "image/png")

