import os
import shutil
import tempfile
import uuid
import aiofiles  # type: ignore[import-untyped]
from typing import Annotated, Dict

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from src.domain.entities.user import User
from src.presentation.api.dependencies.auth import get_current_user

router = APIRouter(prefix="/upload", tags=["upload"])

# Directory to temporarily store uploaded files
TEMP_UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "atenea_uploads")
MAX_FILE_SIZE_MB = 50

@router.post(
    "",
    responses={
        400: {"description": "No filename provided"},
        413: {"description": "File too large"}
    }
)
async def upload_file(
    file: Annotated[UploadFile, File(...)],
    current_user: User = Depends(get_current_user),
) -> Dict[str, str]:
    """
    Sube un archivo de forma temporal para que luego el agente de aprendizaje 
    (o cualquier otro) pueda procesarlo pasándole la ruta.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Create temporary directory if it doesn't exist
    os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

    import re

    # Generate a unique filename and sanitize the stem and extension
    raw_stem, raw_ext = os.path.splitext(file.filename)
    safe_stem = re.sub(r'[^a-zA-Z0-9_\-]', '_', raw_stem).strip('_')
    safe_ext = re.sub(r'[^a-zA-Z0-9.]', '', raw_ext)
    
    unique_filename = f"{uuid.uuid4().hex[:8]}_{safe_stem}{safe_ext}" if safe_stem else f"{uuid.uuid4()}{safe_ext}"
    file_path = os.path.join(TEMP_UPLOAD_DIR, unique_filename)

    # Save the file (we read in chunks to avoid loading large files in memory,
    # and we also check the file size limit)
    size = 0
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024

    async with aiofiles.open(file_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            size += len(chunk)
            if size > max_bytes:
                os.remove(file_path)
                raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB")
            await buffer.write(chunk)

    return {
        "ok": "true",
        "original_filename": file.filename,
        "path": file_path
    }
