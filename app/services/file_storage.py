"""
Local-disk attachment storage for the MVP. Swappable later for S3/Azure Blob
by replacing `save_upload`/`delete_upload`/`resolve_path` without touching
callers, since they only deal with the returned stored_filename.
"""
import os
import uuid
from pathlib import Path

import aiofiles
from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import ValidationFailedError

ALLOWED_CONTENT_TYPES = {
    "image/jpeg", "image/png", "image/webp", "image/heic",
    "video/mp4", "video/quicktime",
    "application/pdf",
}

_storage_dir = Path(settings.STORAGE_DIR)
_storage_dir.mkdir(parents=True, exist_ok=True)


def _safe_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return ext if 0 < len(ext) <= 10 else ""


async def save_upload(file: UploadFile) -> tuple[str, int]:
    """Validates and streams the upload to disk. Returns (stored_filename, size_bytes)."""
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationFailedError(f"Unsupported file type: {file.content_type}")

    stored_filename = f"{uuid.uuid4().hex}{_safe_extension(file.filename or '')}"
    destination = _storage_dir / stored_filename

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    size = 0
    async with aiofiles.open(destination, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                await out.close()
                os.remove(destination)
                raise ValidationFailedError(f"File exceeds the {settings.MAX_UPLOAD_MB}MB limit.")
            await out.write(chunk)

    return stored_filename, size


def resolve_path(stored_filename: str) -> Path:
    path = (_storage_dir / stored_filename).resolve()
    if _storage_dir.resolve() not in path.parents:
        raise ValidationFailedError("Invalid file reference.")
    return path


def delete_upload(stored_filename: str) -> None:
    path = resolve_path(stored_filename)
    if path.exists():
        path.unlink()
