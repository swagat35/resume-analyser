"""
Database engine + session management.
Defaults to SQLite for local dev; point DATABASE_URL at a free
Postgres instance (Neon/Supabase) for production.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables if they don't exist. Call once at startup."""
    from app.db import models  # noqa: F401  (ensures models are registered)
    Base.metadata.create_all(bind=engine)
