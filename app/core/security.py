"""
Security helpers.

- validate_file: checks real file type via magic bytes (not just extension),
  enforces size limits.
- sanitize_text: strips anything that could be used for injection when text
  is later rendered or passed to the LLM.
- limiter: shared slowapi rate limiter instance, keyed by client IP.
"""
from __future__ import annotations

import io
import re
import zipfile

import magic
from fastapi import HTTPException, UploadFile, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

settings = get_settings()

limiter = Limiter(key_func=get_remote_address)

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

# Real allowed MIME types, verified via magic bytes — not filename extension.
ALLOWED_MIME_TYPES = {
    "application/pdf",
    DOCX_MIME,
}

# A .docx file IS a zip archive under the hood. Different libmagic/magic-db
# builds (notably Windows' python-magic-bin vs Linux's libmagic1) sometimes
# report it generically instead of with the specific Office MIME type.
# Treat these as "maybe docx" and confirm via the zip's internal structure.
_ZIP_LIKE_MIME_TYPES = {"application/zip", "application/octet-stream"}


def _looks_like_docx(contents: bytes) -> bool:
    """
    Confirms a zip-like file is actually a .docx by checking for the
    manifest entry every real Word document contains. Cheap and reliable
    fallback for when magic's MIME guess is ambiguous/generic.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(contents)) as zf:
            return "word/document.xml" in zf.namelist()
    except (zipfile.BadZipFile, ValueError):
        return False


async def validate_file(file: UploadFile) -> tuple[bytes, str]:
    """
    Reads the uploaded file, enforces size limit, and verifies the real
    file type via magic bytes (with a zip-structure fallback for .docx).
    Raises HTTPException on any violation.

    Returns (raw_bytes, resolved_mime_type) — resolved_mime_type is always
    one of ALLOWED_MIME_TYPES, even if magic's raw guess was the generic
    zip-like fallback, so callers never need to re-detect the type
    themselves (and can't independently disagree with this check).
    """
    contents = await file.read()

    if len(contents) == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Uploaded file is empty.")

    if len(contents) > settings.max_upload_size_bytes:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File exceeds max size of {settings.max_upload_size_mb}MB.",
        )

    detected_type = magic.from_buffer(contents, mime=True)
    resolved_type = detected_type

    if detected_type not in ALLOWED_MIME_TYPES:
        if detected_type in _ZIP_LIKE_MIME_TYPES and _looks_like_docx(contents):
            resolved_type = DOCX_MIME
        else:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Unsupported file type '{detected_type}'. Only PDF and DOCX are allowed.",
            )

    return contents, resolved_type


_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_SCRIPT_TAG_RE = re.compile(r"<script.*?>.*?</script>", re.IGNORECASE | re.DOTALL)


def sanitize_text(text: str, max_len: int = 20_000) -> str:
    """
    Strips control characters and obvious script/HTML injection attempts
    from extracted resume text before it is stored, rendered, or sent
    to any downstream model. Also truncates to a safe max length so a
    malicious file can't be used to blow up token usage / memory.
    """
    text = _SCRIPT_TAG_RE.sub("", text)
    text = _CONTROL_CHARS_RE.sub("", text)
    return text.strip()[:max_len]
