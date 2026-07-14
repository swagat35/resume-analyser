import io
from unittest.mock import patch

from docx import Document
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _make_docx_bytes(text: str) -> bytes:
    doc = Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@patch("app.api.routes.scorer.analyze")
def test_analyze_success(mock_analyze):
    mock_analyze.return_value = {
        "match_score": 82.5,
        "skill_gap": {"matching_skills": ["python"], "missing_skills": ["kubernetes"]},
        "strengths": ["Strong Python background"],
        "suggestions": ["Add cloud deployment experience"],
        "summary": "Good candidate with room to grow in DevOps.",
    }

    resume_bytes = _make_docx_bytes("Experienced Python developer with FastAPI skills.")
    files = {
        "resume": (
            "resume.docx",
            resume_bytes,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    data = {"job_description": "Looking for a Python engineer with Kubernetes experience."}

    response = client.post("/api/v1/analyze", files=files, data=data)
    assert response.status_code == 200
    body = response.json()
    assert body["match_score"] == 82.5
    assert "python" in body["skill_gap"]["matching_skills"]


def test_analyze_rejects_bad_file_type():
    files = {"resume": ("malicious.exe", b"not a real resume", "application/octet-stream")}
    data = {"job_description": "Looking for a Python engineer with 5+ years experience."}
    response = client.post("/api/v1/analyze", files=files, data=data)
    assert response.status_code == 400


def test_analyze_rejects_short_job_description():
    resume_bytes = _make_docx_bytes("Some resume text")
    files = {
        "resume": (
            "resume.docx",
            resume_bytes,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }
    data = {"job_description": "too short"}
    response = client.post("/api/v1/analyze", files=files, data=data)
    assert response.status_code == 422
