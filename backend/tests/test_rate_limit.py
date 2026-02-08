import os
os.environ.setdefault("DATABASE_URL", "sqlite:///")
os.environ.setdefault("SECRET_KEY", "test-secret")

from backend.app.rate_limit import limiter


def test_limiter_exists():
    """Rate limiter instance is created."""
    assert limiter is not None


def test_limiter_is_limiter_instance():
    """Rate limiter is a slowapi Limiter."""
    from slowapi import Limiter
    assert isinstance(limiter, Limiter)
