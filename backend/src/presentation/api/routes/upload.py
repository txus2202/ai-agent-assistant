from __future__ import annotations

import logging
import os
import re
import tempfile
import time
import uuid
from pathlib import Path
from typing import Annotated, Any, Dict

import aiofiles  # type: ignore[import-untyped]
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from src.domain.entities.user import User
from src.presentation.api.config import Settings, get_settings
from src.presentation.api.dependencies.auth import get_current_user

router = APIRouter(prefix="/upload", tags=["upload"])
logger = logging.getLogger(__name__)

# Base directory to temporarily store uploaded files
TEMP_UPLOAD_DIR = os.path.join(tempfile.gettempdir(), "atenea_uploads")
UPLOAD_TTL_SECONDS = 3600


def _sanitize_user_segment(user_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", user_id).strip("_")
    if not safe:
        raise ValueError("Invalid user identifier for uploads")
    return safe


def get_user_upload_dir(user_id: str) -> Path:
    """Return the resolved, user-scoped temporary upload directory."""
    base_dir = Path(TEMP_UPLOAD_DIR).resolve()
    user_segment = _sanitize_user_segment(user_id)
    user_dir = (base_dir / user_segment).resolve()
    if not user_dir.is_relative_to(base_dir) or user_dir == base_dir:
        raise ValueError("Invalid upload directory")
    return user_dir


def resolve_user_attachment_path(raw_attachment: str, user_id: str | None) -> Path:
    """
    Resolve an attachment identifier or path and ensure it stays strictly
    confined inside the authenticated user's upload directory.
    """
    if not user_id or not user_id.strip():
        raise PermissionError("Authenticated user required for file attachments")
    if not isinstance(raw_attachment, str) or not raw_attachment.strip() or "\x00" in raw_attachment:
        raise ValueError("Invalid attachment path")

    cleaned = raw_attachment.strip()
    user_dir = get_user_upload_dir(user_id)

    if "/" not in cleaned and "\\" not in cleaned:
        candidate = (user_dir / cleaned).resolve()
    else:
        candidate = Path(cleaned).resolve()

    if not candidate.is_relative_to(user_dir) or candidate == user_dir:
        raise PermissionError("Attachment path escapes user upload directory")
    return candidate


def cleanup_expired_uploads(user_dir: Path, ttl_seconds: int = UPLOAD_TTL_SECONDS) -> None:
    """Best-effort removal of expired temporary uploads in ``user_dir``."""
    if not user_dir.exists():
        return
    cutoff = time.time() - ttl_seconds
    for entry in user_dir.iterdir():
        try:
            if entry.is_file() and entry.stat().st_mtime < cutoff:
                entry.unlink(missing_ok=True)
        except OSError:
            logger.warning("Failed to cleanup expired upload %s", entry, exc_info=True)


@router.post(
    "",
    responses={
        400: {"description": "No filename provided"},
        413: {"description": "File too large"},
    },
)
async def upload_file(
    file: Annotated[UploadFile, File(...)],
    current_user: Annotated[User, Depends(get_current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Dict[str, Any]:
    """
    Sube un archivo temporal aislado en el directorio del usuario autenticado
    para su procesamiento posterior por el agente de aprendizaje.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    user_dir = get_user_upload_dir(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    cleanup_expired_uploads(user_dir)

    raw_stem, raw_ext = os.path.splitext(file.filename)
    safe_stem = re.sub(r"[^a-zA-Z0-9_\-]", "_", raw_stem).strip("_")
    safe_ext = re.sub(r"[^a-zA-Z0-9.]", "", raw_ext)

    unique_filename = (
        f"{uuid.uuid4().hex[:8]}_{safe_stem}{safe_ext}"
        if safe_stem
        else f"{uuid.uuid4().hex}{safe_ext}"
    )
    file_path = (user_dir / unique_filename).resolve()
    if not file_path.is_relative_to(user_dir) or file_path == user_dir:
        raise HTTPException(status_code=400, detail="Invalid filename")

    max_file_size_mb = settings.max_learn_file_mb
    max_bytes = max_file_size_mb * 1024 * 1024
    size = 0

    try:
        async with aiofiles.open(file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):  # 1MB chunks
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum size is {max_file_size_mb}MB",
                    )
                await buffer.write(chunk)
    except HTTPException:
        file_path.unlink(missing_ok=True)
        raise
    except Exception:
        file_path.unlink(missing_ok=True)
        raise

    return {
        "ok": True,
        "original_filename": file.filename,
        "attachment_id": unique_filename,
        "path": str(file_path),
    }
