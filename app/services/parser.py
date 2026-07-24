"""
Extracts raw text from uploaded resume files (PDF or DOCX).
Handles corrupt / unreadable files gracefully instead of crashing the app.

PDFs with no extractable text layer (i.e. scanned/image-based resumes) fall
back to OCR via Tesseract. This requires the `tesseract-ocr` system binary
to be installed (see Dockerfile / README for setup) — if it's missing, we
degrade gracefully to the original "no extractable text" error rather than
crashing the request.
"""
from __future__ import annotations

import io

import fitz  # PyMuPDF — used only to rasterize PDF pages for OCR
import pdfplumber
import pytesseract
from docx import Document
from fastapi import HTTPException, status
from PIL import Image

from app.core.logging import get_logger

logger = get_logger(__name__)

# Defense in depth: cap how many pages we'll OCR per request, independent
# of the overall file-size limit, so a crafted many-page PDF can't be used
# to tie up CPU/memory with expensive OCR calls.
MAX_OCR_PAGES = 10
OCR_DPI = 300


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

    if text:
        return text

    # No text layer found — likely a scanned/image-based PDF. Try OCR.
    logger.info("No text layer found in PDF, attempting OCR fallback")
    ocr_text = _ocr_pdf(file_bytes)
    if ocr_text:
        return ocr_text

    raise HTTPException(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        "No extractable text found, even after attempting OCR. This PDF may be "
        "a low-quality scan, blank, or password protected.",
    )


def _ocr_pdf(file_bytes: bytes) -> str:
    """
    Rasterizes each PDF page to an image (via PyMuPDF, no external system
    dependency beyond the Python package itself) and runs Tesseract OCR on
    each page. Returns an empty string — never raises — if OCR isn't
    available or produces nothing, so callers can fall back to a clear
    user-facing error instead of a crash.
    """
    text_parts: list[str] = []
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as pdf:
            for i, page in enumerate(pdf):
                if i >= MAX_OCR_PAGES:
                    logger.warning("PDF exceeds %d pages, truncating OCR", MAX_OCR_PAGES)
                    break
                pixmap = page.get_pixmap(dpi=OCR_DPI)
                image = Image.open(io.BytesIO(pixmap.tobytes("png")))
                text_parts.append(pytesseract.image_to_string(image))
    except pytesseract.TesseractNotFoundError:
        logger.error(
            "Tesseract OCR binary not found — install tesseract-ocr to enable "
            "scanned-PDF support. Falling back to standard error message."
        )
        return ""
    except Exception:
        logger.exception("OCR fallback failed unexpectedly")
        return ""

    return "\n".join(text_parts).strip()


def _extract_docx_text(file_bytes: bytes) -> str:
    doc = Document(io.BytesIO(file_bytes))
    text = "\n".join(p.text for p in doc.paragraphs).strip()
    if not text:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "No extractable text found in this DOCX file."
        )
    return text