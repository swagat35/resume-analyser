"""
Extracts raw text from uploaded resume files (PDF or DOCX).
Handles corrupt / unreadable files gracefully instead of crashing the app.
"""
from __future__ import annotations

import io

import pdfplumber
from docx import Document
from fastapi import HTTPException, status

from app.core.logging import get_logger

logger = get_logger(__name__)


def extract_text(file_bytes: bytes, mime_type: str) -> str:
    try:
        if mime_type == "application/pdf":
            return _extract_pdf_text(file_bytes)
        elif mime_type == (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ):
            return _extract_docx_text(file_bytes)
        else:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Unsupported file type for text extraction."
            )
    except HTTPException:
        raise
    except Exception:
        # Never leak internal parser exceptions/stack traces to the client.
        logger.exception("Failed to parse uploaded resume file")
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Could not read this file. It may be corrupted, scanned as an image, "
            "or password protected. Please upload a text-based PDF or DOCX.",
        )


def _extract_pdf_text(file_bytes: bytes) -> str:
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_parts.append(page_text)
    text = "\n".join(text_parts).strip()
    if not text:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No extractable text found. This PDF may be a scanned image without OCR.",
        )
    return text


def _extract_docx_text(file_bytes: bytes) -> str:
    doc = Document(io.BytesIO(file_bytes))
    text = "\n".join(p.text for p in doc.paragraphs).strip()
    if not text:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "No extractable text found in this DOCX file."
        )
    return text
