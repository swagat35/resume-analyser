import io
import shutil

import pytest
from docx import Document
from fastapi import HTTPException
from PIL import Image, ImageDraw

from app.services.parser import extract_text

TESSERACT_AVAILABLE = shutil.which("tesseract") is not None


def _make_docx_bytes(text: str) -> bytes:
    doc = Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_scanned_pdf_bytes(text: str) -> bytes:
    """
    Builds a PDF containing ONLY a rendered image of the given text — no
    text layer at all — to realistically simulate a scanned resume for
    testing the OCR fallback path.
    """
    import fitz  # local import: only needed by this test helper

    img = Image.new("RGB", (1000, 200), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), text, fill="black")
    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")

    doc = fitz.open()
    page = doc.new_page(width=1000, height=200)
    page.insert_image(fitz.Rect(0, 0, 1000, 200), stream=img_buf.getvalue())
    pdf_buf = io.BytesIO()
    doc.save(pdf_buf)
    doc.close()
    return pdf_buf.getvalue()


def _make_normal_pdf_bytes(text: str) -> bytes:
    """Builds a PDF with a real text layer (not scanned) for contrast tests."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), text)
    buf = io.BytesIO()
    doc.save(buf)
    doc.close()
    return buf.getvalue()


def test_extract_docx_text_success():
    content = _make_docx_bytes("John Doe - Python Developer with 5 years experience")
    text = extract_text(
        content,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert "Python Developer" in text


def test_extract_docx_empty_raises():
    content = _make_docx_bytes("")
    with pytest.raises(HTTPException) as exc_info:
        extract_text(
            content,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    assert exc_info.value.status_code == 422


def test_unsupported_mime_type_raises():
    with pytest.raises(HTTPException) as exc_info:
        extract_text(b"not a real file", "text/plain")
    assert exc_info.value.status_code == 400


def test_corrupt_pdf_does_not_crash():
    with pytest.raises(HTTPException) as exc_info:
        extract_text(b"%PDF-1.4 corrupted garbage not a real pdf", "application/pdf")
    assert exc_info.value.status_code == 422


def test_normal_pdf_uses_text_layer_not_ocr():
    content = _make_normal_pdf_bytes("Regular text-based resume, not scanned.")
    text = extract_text(content, "application/pdf")
    assert "Regular text-based resume" in text


@pytest.mark.skipif(
    not TESSERACT_AVAILABLE, reason="tesseract-ocr binary not installed in this environment"
)
def test_scanned_pdf_falls_back_to_ocr():
    content = _make_scanned_pdf_bytes("Python Developer resume")
    text = extract_text(content, "application/pdf")
    # OCR isn't pixel-perfect, so check for a recognizable substring rather
    # than an exact match.
    assert "Python" in text or "Developer" in text


def test_scanned_pdf_without_tesseract_gives_clear_error(monkeypatch):
    """
    Simulates Tesseract not being installed (e.g. a bare Windows dev machine
    that hasn't installed it yet) — confirms this degrades to a clear 422
    error instead of crashing the request.
    """
    import pytesseract

    monkeypatch.setattr(pytesseract.pytesseract, "tesseract_cmd", "/nonexistent/tesseract")

    content = _make_scanned_pdf_bytes("Python Developer resume")
    with pytest.raises(HTTPException) as exc_info:
        extract_text(content, "application/pdf")
    assert exc_info.value.status_code == 422
