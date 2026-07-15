

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import limiter, sanitize_text, validate_file
from app.db.database import get_db
from app.models.schemas import AnalyzeResponse, HealthResponse
from app.services import parser, scorer

router = APIRouter()
logger = get_logger(__name__)
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    return HealthResponse(status="ok", environment=settings.environment)


@router.post("/analyze", response_model=AnalyzeResponse)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def analyze_resume(
    request: Request,
    resume: UploadFile = File(...),
    job_description: str = Form(..., min_length=20, max_length=10_000),
    db: Session = Depends(get_db),
):
    """
    Accepts a resume file (PDF/DOCX) and a job description, returns a
    structured match score, skill gap analysis, and improvement suggestions.
    """
    file_bytes = await validate_file(resume)

    import magic
    mime_type = magic.from_buffer(file_bytes, mime=True)

    raw_text = parser.extract_text(file_bytes, mime_type)
    resume_text = sanitize_text(raw_text)
    clean_jd = sanitize_text(job_description)

    logger.info(
        "Analyze request received | resume_bytes=%d | jd_len=%d",
        len(file_bytes), len(clean_jd),
    )

    result = scorer.analyze(resume_text, clean_jd, db=db)
    return AnalyzeResponse(**result)
