from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.auth import (
    create_access_token,
    get_current_user,
    get_current_user_optional,
    hash_password,
    verify_password,
)
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import limiter, sanitize_text, validate_file
from app.db.database import get_db
from app.db.models import AnalysisRecord, User
from app.models.schemas import (
    AnalyzeResponse,
    HealthResponse,
    HistoryItem,
    Token,
    UserCreate,
    UserOut,
)
from app.services import parser, scorer

router = APIRouter()
logger = get_logger(__name__)
settings = get_settings()


@router.get("/health", response_model=HealthResponse)
@router.head("/health", include_in_schema=False)
async def health_check():
    return HealthResponse(status="ok", environment=settings.environment)


# --- Auth ---

@router.post("/auth/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def register(request: Request, payload: UserCreate, db: Session = Depends(get_db)):
    """Creates a new user account. Passwords are hashed with bcrypt, never stored in plaintext."""
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "An account with this email already exists.")

    user = User(email=payload.email, hashed_password=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/auth/login", response_model=Token)
@limiter.limit("10/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    OAuth2-compatible token login. `form_data.username` is treated as the
    email (OAuth2PasswordRequestForm always calls the field "username").
    """
    user = db.query(User).filter(User.email == form_data.username).first()
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(subject=user.email)
    return Token(access_token=access_token)


@router.get("/auth/me", response_model=UserOut)
async def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


# --- Resume analysis ---

@router.post("/analyze", response_model=AnalyzeResponse)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def analyze_resume(
    request: Request,
    resume: UploadFile = File(...),
    job_description: str = Form(..., min_length=20, max_length=10_000),
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_current_user_optional),
):
    """
    Accepts a resume file (PDF/DOCX) and a job description, returns a
    structured match score, skill gap analysis, and improvement suggestions.

    Works anonymously. If called with a valid Bearer token, the result is
    also linked to that user's account and appears in GET /history.
    """
    file_bytes, mime_type = await validate_file(resume)

    raw_text = parser.extract_text(file_bytes, mime_type)
    resume_text = sanitize_text(raw_text)
    clean_jd = sanitize_text(job_description)

    logger.info(
        "Analyze request received | resume_bytes=%d | jd_len=%d | user=%s",
        len(file_bytes), len(clean_jd), current_user.id if current_user else "anonymous",
    )

    user_id = current_user.id if current_user else None
    result = scorer.analyze(resume_text, clean_jd, db=db, user_id=user_id)
    return AnalyzeResponse(**result)


# --- History ---

@router.get("/history", response_model=list[HistoryItem])
async def get_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 20,
):
    """
    Returns the logged-in user's past analysis scores (most recent first).
    Requires authentication — this is the one endpoint that needs a valid
    Bearer token, since it exposes account-specific data.
    """
    limit = max(1, min(limit, 100))
    records = (
        db.query(AnalysisRecord)
        .filter(AnalysisRecord.user_id == current_user.id)
        .order_by(AnalysisRecord.created_at.desc())
        .limit(limit)
        .all()
    )
    return records
