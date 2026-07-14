"""
ORM models.

By design we do NOT persist raw resume text or the raw job description —
only a hashed fingerprint (for cache/dedup) and the derived, non-identifying
result metrics. This keeps user PII out of the database by default.
"""
import datetime as dt

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base


class AnalysisRecord(Base):
    __tablename__ = "analysis_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # SHA-256 of (resume_text + job_description), used for cache lookups only.
    request_hash: Mapped[str] = mapped_column(String(64), index=True, unique=True)
    match_score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)
