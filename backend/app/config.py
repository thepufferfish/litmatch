import os

SECRET_KEY = os.environ.get("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable must be set")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable must be set")

CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",")

REFRESH_COOKIE_PATH = os.environ.get("REFRESH_COOKIE_PATH", "/auth/refresh")

# Cookie security: default to True (secure by default), set to false only for local dev
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "true").lower() == "true"
