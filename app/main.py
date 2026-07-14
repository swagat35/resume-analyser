"""
FastAPI application entrypoint.

Run locally:
    uvicorn app.main:app --reload

Production:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.routes import router
from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.core.security import limiter
from app.db.database import init_db

settings = get_settings()
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Application startup complete | environment=%s", settings.environment)
    yield


app = FastAPI(
    title="AI Resume Analyzer",
    description="Analyzes resumes against job descriptions using local NLP + a free-tier LLM.",
    version="1.0.0",
    docs_url="/docs" if not settings.is_production else None,  # hide docs in prod
    redoc_url=None,
    lifespan=lifespan,
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — explicit allow-list, never "*"
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Catch-all so an unexpected error never leaks a stack trace to the client
    # and never crashes the worker process.
    logger.exception("Unhandled exception on %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Please try again later."},
    )
