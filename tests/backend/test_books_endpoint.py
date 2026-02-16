"""Unit tests for the /books/ endpoint security fix and new /users/me/rated-books/ endpoint.

Verifies that:
1. The user_id query parameter is NOT accepted on the public /books/ endpoint
   (prevents enumeration of other users' rated books -- IDOR vulnerability).
2. A new authenticated endpoint GET /users/me/rated-books/ exists and returns
   only the current user's rated books with proper pagination and sorting.
"""

import inspect
import os

# Ensure required env vars are set before importing config.
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-only")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app, get_current_user, get_session, read_books
from backend.db.models import (
    Author,
    Book,
    User,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_user() -> User:
    """A mock authenticated user."""
    user = User(id=10, username="testuser", password_hash="hashed")
    return user


@pytest.fixture
def mock_author() -> Author:
    return Author(id=1, name="Test Author")


@pytest.fixture
def mock_books(mock_author: Author) -> list[Book]:
    """Sample books for testing."""
    return [
        Book(
            id=1,
            title="Book One",
            author_id=1,
            publisher_id=None,
            publish_date=None,
            description="First book",
            url="https://example.com/book1",
            cover=None,
            author=mock_author,
        ),
        Book(
            id=2,
            title="Book Two",
            author_id=1,
            publisher_id=None,
            publish_date=None,
            description="Second book",
            url="https://example.com/book2",
            cover=None,
            author=mock_author,
        ),
    ]


def _create_mock_session(books: list[Book] | None = None, total: int = 0):
    """Build a mock SQLModel session that returns predictable results.

    The mock supports chained calls like:
        session.exec(stmt.offset(n).limit(m)).all()
        session.exec(count_stmt).one()
    """
    session = MagicMock()

    # Chained .offset().limit().all() returns books list
    offset_mock = MagicMock()
    limit_mock = MagicMock()
    limit_mock.all.return_value = books or []
    offset_mock.limit.return_value = limit_mock

    # First call to session.exec -> the count query (supports .one)
    # Second call to session.exec -> the data query (supports .offset)
    data_result = MagicMock()
    data_result.offset.return_value = offset_mock
    data_result.all.return_value = books or []

    count_result = MagicMock()
    count_result.one.return_value = total

    # exec returns different mocks depending on call order
    session.exec.side_effect = [count_result, data_result]

    return session


@pytest.fixture
def client(mock_user: User):
    """TestClient that overrides auth and session dependencies."""

    def _override_get_current_user():
        return mock_user

    def _override_get_session():
        session = _create_mock_session(books=[], total=0)
        yield session

    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[get_session] = _override_get_session

    test_client = TestClient(app, raise_server_exceptions=False)
    yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def unauthenticated_client():
    """TestClient with NO auth override -- requests lack a Bearer token."""

    def _override_get_session():
        session = _create_mock_session(books=[], total=0)
        yield session

    app.dependency_overrides[get_session] = _override_get_session

    test_client = TestClient(app, raise_server_exceptions=False)
    yield test_client

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests: /books/ endpoint should NOT accept user_id
# ---------------------------------------------------------------------------


class TestBooksEndpointNoUserId:
    """Verify user_id parameter was removed from /books/ endpoint."""

    def test_read_books_function_has_no_user_id_parameter(self):
        """The read_books function should not accept a user_id parameter."""
        sig = inspect.signature(read_books)
        param_names = set(sig.parameters.keys())
        assert "user_id" not in param_names, (
            "read_books should not have a user_id parameter -- "
            "it exposes other users' rated books"
        )

    def test_openapi_schema_books_has_no_user_id(self):
        """The OpenAPI schema for /books/ should not include user_id."""
        schema = app.openapi()
        books_path = schema["paths"].get("/books/", {})
        get_op = books_path.get("get", {})
        parameters = get_op.get("parameters", [])
        param_names = {p.get("name") for p in parameters}
        assert "user_id" not in param_names, (
            "/books/ OpenAPI schema should not expose user_id parameter"
        )

    def test_books_endpoint_ignores_user_id_query_param(self, client):
        """GET /books/?user_id=999 should return a normal response
        without filtering by user_id (the parameter is ignored)."""
        response = client.get("/books/", params={"user_id": 999})
        # Should succeed (200) but not filter by user_id
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tests: GET /users/me/rated-books/ (new authenticated endpoint)
# ---------------------------------------------------------------------------


class TestUserRatedBooksEndpoint:
    """Tests for the new GET /users/me/rated-books/ endpoint."""

    def test_rated_books_without_auth_returns_401(self, unauthenticated_client):
        """GET /users/me/rated-books/ without a Bearer token should return 401."""
        response = unauthenticated_client.get("/users/me/rated-books/")
        assert response.status_code in (401, 403), (
            f"Expected 401 or 403 for unauthenticated request, "
            f"got {response.status_code}"
        )

    def test_rated_books_with_auth_returns_200(self, client):
        """GET /users/me/rated-books/ with valid auth should return 200."""
        response = client.get("/users/me/rated-books/")
        assert response.status_code == 200

    def test_rated_books_response_shape(self, client):
        """Response should match PaginatedResponse[BookRead] shape."""
        response = client.get("/users/me/rated-books/")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)

    def test_rated_books_default_pagination(self, client):
        """Without pagination params, page=1 and limit=24 should be defaults."""
        response = client.get("/users/me/rated-books/")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["limit"] == 24

    def test_rated_books_custom_pagination(self, client):
        """Custom page and limit should be respected."""
        response = client.get(
            "/users/me/rated-books/", params={"page": 2, "limit": 10}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 2
        assert data["limit"] == 10

    def test_rated_books_sort_parameter_accepted(self, client):
        """The sort query parameter should be accepted."""
        response = client.get(
            "/users/me/rated-books/", params={"sort": "title_asc"}
        )
        assert response.status_code == 200

    def test_rated_books_invalid_sort_returns_422(self, client):
        """An invalid sort value should return 422."""
        response = client.get(
            "/users/me/rated-books/", params={"sort": "invalid_sort"}
        )
        assert response.status_code == 422

    def test_rated_books_page_validation(self, client):
        """page < 1 should return 422."""
        response = client.get(
            "/users/me/rated-books/", params={"page": 0}
        )
        assert response.status_code == 422

    def test_rated_books_limit_validation(self, client):
        """limit > 100 should return 422."""
        response = client.get(
            "/users/me/rated-books/", params={"limit": 101}
        )
        assert response.status_code == 422

    def test_rated_books_endpoint_exists_in_openapi(self):
        """The /users/me/rated-books/ endpoint should exist in OpenAPI schema."""
        schema = app.openapi()
        assert "/users/me/rated-books/" in schema["paths"], (
            "/users/me/rated-books/ endpoint should be registered in the app"
        )

    def test_rated_books_openapi_requires_auth(self):
        """The OpenAPI schema should show authentication is required."""
        schema = app.openapi()
        rated_books_path = schema["paths"].get("/users/me/rated-books/", {})
        get_op = rated_books_path.get("get", {})
        # FastAPI marks auth-required endpoints with security schemes
        assert "security" in get_op or any(
            "Authorization" in str(p) for p in get_op.get("parameters", [])
        ), "Endpoint should require authentication"


# ---------------------------------------------------------------------------
# Tests: GET /books/ with category filter
# ---------------------------------------------------------------------------


class TestBooksCategoryFilter:
    """Tests for the category query parameter on /books/ endpoint."""

    def test_books_category_fiction_accepted(self, client):
        """GET /books/?category=fiction should be accepted."""
        response = client.get("/books/", params={"category": "fiction"})
        assert response.status_code == 200

    def test_books_category_nonfiction_accepted(self, client):
        """GET /books/?category=nonfiction should be accepted."""
        response = client.get("/books/", params={"category": "nonfiction"})
        assert response.status_code == 200

    def test_books_no_category_accepted(self, client):
        """GET /books/ without category parameter should work."""
        response = client.get("/books/")
        assert response.status_code == 200

    def test_books_category_combined_with_genre_filter(self, client):
        """category parameter should work with existing genre parameter."""
        response = client.get(
            "/books/", params={"category": "fiction", "genre": 1}
        )
        assert response.status_code == 200

    def test_books_invalid_category_returns_422(self, client):
        """Invalid category value should return 422."""
        response = client.get("/books/", params={"category": "invalid"})
        assert response.status_code == 422

    def test_books_category_parameter_exists_in_openapi(self):
        """The category parameter should be documented in OpenAPI schema."""
        schema = app.openapi()
        books_path = schema["paths"].get("/books/", {})
        get_op = books_path.get("get", {})
        parameters = get_op.get("parameters", [])
        param_names = {p.get("name") for p in parameters}
        assert "category" in param_names, (
            "/books/ OpenAPI schema should include category parameter"
        )

    def test_read_books_function_has_category_parameter(self):
        """The read_books function should accept a category parameter."""
        sig = inspect.signature(read_books)
        param_names = set(sig.parameters.keys())
        assert "category" in param_names, (
            "read_books should have a category parameter"
        )
