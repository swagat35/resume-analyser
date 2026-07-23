"""
Authentication helpers: password hashing (bcrypt) and JWT access token
creation/verification.

Design notes:
- Passwords are never stored in plaintext — only bcrypt hashes.
- JWTs are stateless: no server-side session store needed, so this
  stays compatible with the app's stateless/horizontally-scalable design.
- `get_current_user` is REQUIRED auth (used for /history).
- `get_current_user_optional` is OPTIONAL auth (used for /analyze, so
  anonymous users can still use the core feature, but logged-in users
  get their results saved to history).
"""
from __future__ import annotations

import datetime as dt

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.database import get_db
from app.db.models import User

settings = get_settings()

# auto_error=False so /analyze can accept requests with no token at all
# (anonymous use), while /history still enforces a valid token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

_BCRYPT_MAX_BYTES = 72  # bcrypt silently ignores/rejects anything past this


def hash_password(password: str) -> str:
    truncated = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(truncated, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    truncated = plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    try:
        return bcrypt.checkpw(truncated, hashed_password.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str) -> str:
    """Creates a signed JWT with the user's email as `sub` and an expiry."""
    expire = dt.datetime.now(dt.timezone.utc) + dt.timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _decode_token(token: str) -> str | None:
    """Returns the subject (email) if valid, else None. Never raises."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return payload.get("sub")
    except JWTError:
        return None


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """Required auth dependency — raises 401 if no valid token is present."""
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise credentials_error

    email = _decode_token(token)
    if email is None:
        raise credentials_error

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_error
    return user


def get_current_user_optional(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User | None:
    """Optional auth dependency — returns None instead of raising if absent/invalid."""
    if token is None:
        return None
    email = _decode_token(token)
    if email is None:
        return None
    return db.query(User).filter(User.email == email).first()