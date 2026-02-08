import os

# Set DATABASE_URL to sqlite before importing app to avoid psycopg2 dependency
os.environ.setdefault("DATABASE_URL", "sqlite:///")

from fastapi.testclient import TestClient
from backend.app.main import app, escape_like

client = TestClient(app)


def test_search_empty_query_returns_400():
    response = client.get("/books/search", params={"q": ""})
    assert response.status_code == 400


def test_search_short_query_returns_400():
    response = client.get("/books/search", params={"q": "a"})
    assert response.status_code == 400


def test_search_missing_query_returns_400():
    response = client.get("/books/search")
    assert response.status_code == 400


def test_escape_like_escapes_wildcards():
    assert escape_like("%") == "\\%"
    assert escape_like("_") == "\\_"
    assert escape_like("\\") == "\\\\"
    assert escape_like("test%") == "test\\%"
    assert escape_like("te_st") == "te\\_st"
    assert escape_like("100%") == "100\\%"
    assert escape_like("normal") == "normal"
