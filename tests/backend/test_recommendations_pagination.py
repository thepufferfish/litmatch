"""Unit tests for paginated recommendations endpoint.

Verifies that:
1. The offset query parameter is accepted on GET /recommendations/
2. A hard cap of 100 total results is enforced
3. has_more is true when more results exist, false otherwise
4. The response includes total, offset, limit, has_more fields
5. Edge cases: offset beyond total, offset + limit > 100
"""

import os

# Ensure required env vars are set before importing config.
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-only")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app, get_current_user, get_session
from backend.app.rate_limit import limiter
from backend.db.models import (
    Author,
    Book,
    BookRead,
    Genre,
    User,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_user() -> User:
    """A mock authenticated user."""
    return User(id=10, username="testuser", password_hash="hashed")


@pytest.fixture
def mock_author() -> Author:
    return Author(id=1, name="Test Author")


def _make_book(book_id: int, mock_author: Author) -> Book:
    """Create a mock Book with the given ID."""
    book = Book(
        id=book_id,
        title=f"Book {book_id}",
        author_id=1,
        publisher_id=None,
        publish_date=None,
        description=f"Description {book_id}",
        url=f"https://example.com/book{book_id}",
        cover=None,
        author=mock_author,
    )
    book.genres = []
    book.reviews = []
    return book


def _make_book_read(book_id: int) -> BookRead:
    """Create a BookRead for mock annotate return values."""
    return BookRead(
        id=book_id,
        title=f"Book {book_id}",
        author_id=1,
        publisher_id=None,
        publish_date=None,
        description=f"Description {book_id}",
        url=f"https://example.com/book{book_id}",
        cover=None,
        author=None,
        publisher=None,
        genres=[],
        avg_critic_rating=None,
        review_count=0,
    )


def _create_mock_session(rated_book_ids: list[int] | None = None):
    """Build a mock SQLModel session."""
    session = MagicMock()
    result = MagicMock()
    result.all.return_value = rated_book_ids or []
    session.exec.return_value = result
    session.get.return_value = None
    return session


@pytest.fixture
def client(mock_user: User):
    """TestClient that overrides auth and session dependencies."""
    limiter.enabled = False

    def _override_get_current_user():
        return mock_user

    def _override_get_session():
        session = _create_mock_session(rated_book_ids=[])
        yield session

    app.dependency_overrides[get_current_user] = _override_get_current_user
    app.dependency_overrides[get_session] = _override_get_session

    test_client = TestClient(app, raise_server_exceptions=False)
    yield test_client

    app.dependency_overrides.clear()
    limiter.enabled = True


# ---------------------------------------------------------------------------
# Tests: Paginated response shape
# ---------------------------------------------------------------------------


class TestPaginatedResponseShape:
    """Tests that the recommendations endpoint returns paginated response."""

    @patch("backend.app.main.get_popular_books")
    @patch("backend.app.main._annotate_books_with_ratings")
    def test_response_contains_pagination_fields(
        self, mock_annotate, mock_get_popular, client, mock_author
    ):
        """Response should include total, offset, limit, has_more fields."""
        books = [_make_book(i, mock_author) for i in range(1, 6)]
        mock_get_popular.return_value = (books, 25)
        mock_annotate.return_value = [_make_book_read(i) for i in range(1, 6)]

        response = client.get("/recommendations/")
        assert response.status_code == 200

        data = response.json()
        assert "items" in data
        assert "meta" in data
        assert "total" in data
        assert "offset" in data
        assert "limit" in data
        assert "has_more" in data

    @patch("backend.app.main.get_popular_books")
    @patch("backend.app.main._annotate_books_with_ratings")
    def test_default_offset_is_zero(
        self, mock_annotate, mock_get_popular, client
    ):
        """Default offset should be 0."""
        mock_get_popular.return_value = ([], 0)
        mock_annotate.return_value = []

        response = client.get("/recommendations/")
        assert response.status_code == 200

        data = response.json()
        assert data["offset"] == 0

    @patch("backend.app.main.get_popular_books")
    @patch("backend.app.main._annotate_books_with_ratings")
    def test_offset_parameter_is_passed(
        self, mock_annotate, mock_get_popular, client
    ):
        """Explicit offset should appear in the response."""
        mock_get_popular.return_value = ([], 0)
        mock_annotate.return_value = []

        response = client.get("/recommendations/", params={"offset": 20})
        assert response.status_code == 200

        data = response.json()
        assert data["offset"] == 20


# ---------------------------------------------------------------------------
# Tests: has_more logic
# ---------------------------------------------------------------------------


class TestHasMoreLogic:
    """Tests for has_more field correctness."""

    @patch("backend.app.main.get_popular_books")
    @patch("backend.app.main._annotate_books_with_ratings")
    def test_has_more_true_when_more_results_exist(
        self, mock_annotate, mock_get_popular, client, mock_author
    ):
        """has_more should be true when offset + limit < total and < 100."""
        books = [_make_book(i, mock_author) for i in range(1, 21)]
        mock_get_popular.return_value = (books, 50)
        mock_annotate.return_value = [_make_book_read(i) for i in range(1, 21)]

        response = client.get(
            "/recommendations/", params={"limit": 20, "offset": 0}
        )
        data = response.json()
        assert data["has_more"] is True

    @patch("backend.app.main.get_popular_books")
    @patch("backend.app.main._annotate_books_with_ratings")
    def test_has_more_false_when_no_more_results(
        self, mock_annotate, mock_get_popular, client, mock_author
    ):
        """has_more should be false when offset + limit >= total."""
        books = [_make_book(i, mock_author) for i in range(1, 6)]
        mock_get_popular.return_value = (books, 5)
        mock_annotate.return_value = [_make_book_read(i) for i in range(1, 6)]

        response = client.get(
            "/recommendations/", params={"limit": 20, "offset": 0}
        )
        data = response.json()
        assert data["has_more"] is False

    @patch("backend.app.main.get_popular_books")
    @patch("backend.app.main._annotate_books_with_ratings")
    def test_has_more_false_at_cap_boundary(
        self, mock_annotate, mock_get_popular, client, mock_author
    ):
        """has_more should be false when offset + limit reaches the 100 cap."""
        books = [_make_book(i, mock_author) for i in range(1, 21)]
        mock_get_popular.return_value = (books, 200)
        mock_annotate.return_value = [_make_book_read(i) for i in range(1, 21)]

        response = client.get(
            "/recommendations/", params={"limit": 20, "offset": 80}
        )
        data = response.json()
        assert data["has_more"] is False


# ---------------------------------------------------------------------------
# Tests: Hard cap at 100
# ---------------------------------------------------------------------------


class TestHardCapAt100:
    """Tests that recommendations are capped at 100 total results."""

    def test_offset_at_100_returns_empty(self, client):
        """Offset >= 100 should return empty items without calling DB."""
        response = client.get(
            "/recommendations/", params={"offset": 100, "limit": 20}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["has_more"] is False

    def test_offset_beyond_100_returns_422(self, client):
        """Offset > 100 should return 422 validation error."""
        response = client.get(
            "/recommendations/", params={"offset": 120, "limit": 20}
        )
        assert response.status_code == 422

    @patch("backend.app.main.get_popular_books")
    @patch("backend.app.main._annotate_books_with_ratings")
    def test_limit_clamped_to_not_exceed_100(
        self, mock_annotate, mock_get_popular, client, mock_author
    ):
        """When offset=90 and limit=20, effective limit should be 10."""
        books = [_make_book(i, mock_author) for i in range(1, 11)]
        mock_get_popular.return_value = (books, 200)
        mock_annotate.return_value = [_make_book_read(i) for i in range(1, 11)]

        response = client.get(
            "/recommendations/", params={"offset": 90, "limit": 20}
        )
        assert response.status_code == 200
        data = response.json()

        # The effective limit should be reflected in the response
        assert data["limit"] == 10


# ---------------------------------------------------------------------------
# Tests: Offset validation
# ---------------------------------------------------------------------------


class TestOffsetValidation:
    """Tests for offset parameter validation."""

    def test_negative_offset_returns_422(self, client):
        """Negative offset should return 422."""
        response = client.get("/recommendations/", params={"offset": -1})
        assert response.status_code == 422

    def test_non_integer_offset_returns_422(self, client):
        """Non-integer offset should return 422."""
        response = client.get("/recommendations/", params={"offset": "abc"})
        assert response.status_code == 422

    @patch("backend.app.main.get_popular_books")
    @patch("backend.app.main._annotate_books_with_ratings")
    def test_zero_offset_is_valid(
        self, mock_annotate, mock_get_popular, client
    ):
        """Zero offset should be valid."""
        mock_get_popular.return_value = ([], 0)
        mock_annotate.return_value = []

        response = client.get("/recommendations/", params={"offset": 0})
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Tests: OpenAPI schema
# ---------------------------------------------------------------------------


class TestPaginationOpenAPISchema:
    """Tests for OpenAPI schema updates."""

    def test_offset_parameter_in_openapi_schema(self):
        """The offset parameter should be in the OpenAPI schema."""
        schema = app.openapi()
        recs_path = schema["paths"].get("/recommendations/", {})
        get_op = recs_path.get("get", {})
        parameters = get_op.get("parameters", [])
        param_names = {p.get("name") for p in parameters}
        assert "offset" in param_names
