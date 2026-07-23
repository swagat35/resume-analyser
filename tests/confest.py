"""
Test session setup.

IMPORTANT: this must set DATABASE_URL (and other required env vars) BEFORE
anything from `app` is imported anywhere in the test suite. Several modules
call get_settings() at import time (e.g. app.core.security), and
pydantic-settings only re-reads the environment once per process — so if
the real .env's DATABASE_URL got read first, tests would run against your
actual local/production-like database file instead of a throwaway one.
That was causing failures like "email already exists" across separate
test runs, since data from a previous run was still sitting in
resume_analyzer.db.
"""
import os
import tempfile

_TEST_DB_FD, _TEST_DB_PATH = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ.setdefault("GROQ_API_KEY", "test-key-not-real")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-not-real")

import pytest  # noqa: E402

from app.core.security import limiter  # noqa: E402


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """
    slowapi's Limiter keeps an in-memory store keyed by client IP. Since
    TestClient always uses the same fake IP, rate-limit counts would
    otherwise leak across test functions and cause unrelated tests to
    fail with 429s. Reset the storage before every test for isolation.
    """
    limiter.reset()
    yield


def pytest_sessionfinish(session, exitstatus):
    """Clean up the temporary test database file after the whole run."""
    try:
        os.close(_TEST_DB_FD)
        os.remove(_TEST_DB_PATH)
    except OSError:
        pass
