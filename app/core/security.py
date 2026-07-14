"""
Security helpers.

- validate_file: checks real file type via magic bytes (not just extension),
  enforces size limits.
- sanitize_text: strips anything that could be used for injection when text
  is later rendered or passed to the LLM.
- limiter: shared slowapi rate limiter instance, keyed by client IP.
"""
from __future__ import annotations

import re

import magic
from fastapi import HTTPException, UploadFile, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

settings = get_settings()

limiter = Limiter(key_func=get_remote_address)

# Real allowed MIME types, verified via magic bytes — not filename extension.
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
}


async def validate_file(file: UploadFile) -> bytes:
    """
    Reads the uploaded file, enforces size limit, and verifies the real
    file type via magic bytes. Raises HTTPException on any violation.
    Returns the raw file bytes if valid.
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
    if detected_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Unsupported file type '{detected_type}'. Only PDF and DOCX are allowed.",
        )

    return contents


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
