"""Shared test configuration and fixtures."""
import os

# Set environment variables before importing any app modules
os.environ.setdefault("DATABASE_URL", "sqlite:///")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing")
os.environ.setdefault("COOKIE_SECURE", "false")  # TestClient doesn't support secure cookies
