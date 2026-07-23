import pytest

from app.core.security import limiter


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
