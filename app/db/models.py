"""
ORM models.

By design we do NOT persist raw resume text or the raw job description —
only a hashed fingerprint (for cache/dedup) and the derived, non-identifying
result metrics. This keeps user PII out of the database by default.

AnalysisRecord.user_id is nullable: anonymous (unauthenticated) users can
still use /analyze without an account; only logged-in users get their
results linked for /history.
"""
import datetime as dt

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    analyses: Mapped[list["AnalysisRecord"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class AnalysisRecord(Base):
    __tablename__ = "analysis_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    request_hash: Mapped[str] = mapped_column(String(64), index=True, unique=True)
    match_score: Mapped[float] = mapped_column(Float)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=dt.datetime.utcnow)

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    user: Mapped["User | None"] = relationship(back_populates="analyses")