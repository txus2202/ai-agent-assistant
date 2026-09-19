import os
import shutil
import uuid
from typing import Dict

from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter(prefix="/api/upload", tags=["upload"])

# Directory to temporarily store uploaded files
TEMP_UPLOAD_DIR = "/tmp/atenea_uploads"
MAX_FILE_SIZE_MB = 50

@router.post("")
async def upload_file(file: UploadFile = File(...)) -> Dict[str, str]:
    """
    Sube un archivo de forma temporal para que luego el agente de aprendizaje 
    (o cualquier otro) pueda procesarlo pasándole la ruta.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    # Create temporary directory if it doesn't exist
    os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

    # Generate a unique filename to prevent collisions
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(TEMP_UPLOAD_DIR, unique_filename)

    # Save the file (we read in chunks to avoid loading large files in memory,
    # and we also check the file size limit)
    size = 0
    max_bytes = MAX_FILE_SIZE_MB * 1024 * 1024

    with open(file_path, "wb") as buffer:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            size += len(chunk)
            if size > max_bytes:
                os.remove(file_path)
                raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {MAX_FILE_SIZE_MB}MB")
            buffer.write(chunk)

    return {
        "ok": "true",
        "original_filename": file.filename,
        "path": file_path
    }
