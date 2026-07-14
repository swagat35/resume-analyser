import io

import pytest
from docx import Document
from fastapi import HTTPException

from app.services.parser import extract_text


def _make_docx_bytes(text: str) -> bytes:
    doc = Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
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
