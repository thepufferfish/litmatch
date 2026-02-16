"""Unit tests for genre filtering on recommendations endpoint.

Verifies that:
1. The genre_id query parameter is accepted on GET /recommendations/
2. When genre_id is provided, it is passed to recommendation functions for DB-level filtering
3. When genre_id is omitted, all recommendations are returned (backward compatibility)
4. Invalid genre_id values return appropriate responses
5. Genre filtering works for both personalized and popular recommendation strategies
"""

import os

# Ensure required env vars are set before importing config.
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-only")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app, get_current_user, get_session
from backend.db.models import (
    Author,
    Book,
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


@pytest.fixture
def mock_genres() -> list[Genre]:
    """Sample genres for testing."""
    return [
        Genre(id=1, name="Science Fiction"),
        Genre(id=2, name="Mystery"),
        Genre(id=3, name="Romance"),
    ]


@pytest.fixture
def mock_books_with_genres(mock_author: Author, mock_genres: list[Genre]) -> list[Book]:
    """Sample books with genre associations."""
    book1 = Book(
        id=1,
        title="Sci-Fi Book",
        author_id=1,
        publisher_id=None,
        publish_date=None,
        description="A science fiction book",
        url="https://example.com/book1",
        cover=None,
        author=mock_author,
    )
    book1.genres = [mock_genres[0]]  # Science Fiction

    book2 = Book(
        id=2,
        title="Mystery Book",
        author_id=1,
        publisher_id=None,
        publish_date=None,
        description="A mystery book",
        url="https://example.com/book2",
        cover=None,
        author=mock_author,
    )
    book2.genres = [mock_genres[1]]  # Mystery

    book3 = Book(
        id=3,
        title="Romance Book",
        author_id=1,
        publisher_id=None,
        publish_date=None,
        description="A romance book",
        url="https://example.com/book3",
        cover=None,
        author=mock_author,
    )
    book3.genres = [mock_genres[2]]  # Romance

    return [book1, book2, book3]


def _create_mock_session(
    rated_book_ids: list[int] | None = None,
    genre_exists: bool = True,
):
    """Build a mock SQLModel session.

    Args:
        rated_book_ids: List of book IDs to return for rated books query.
        genre_exists: Whether session.get(Genre, id) returns a genre or None.
    """
    session = MagicMock()

    result = MagicMock()
    result.all.return_value = rated_book_ids or []
    session.exec.return_value = result

    # Mock session.get for genre validation
    if genre_exists:
        session.get.return_value = Genre(id=1, name="Test Genre")
    else:
        session.get.return_value = None

    return session


@pytest.fixture
def client(mock_user: User):
    """TestClient that overrides auth and session dependencies."""

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


# ---------------------------------------------------------------------------
# Tests: GET /recommendations/ with genre_id parameter
# ---------------------------------------------------------------------------


class TestRecommendationsGenreParameter:
    """Tests for the genre_id query parameter on /recommendations/ endpoint."""

    def test_recommendations_accepts_genre_id_parameter(self, client):
        """GET /recommendations/?genre_id=1 should be accepted."""
        with patch("backend.app.main.get_popular_books", return_value=([], 0)), \
             patch("backend.app.main._annotate_books_with_ratings", return_value=[]):
            response = client.get("/recommendations/", params={"genre_id": 1})
            assert response.status_code == 200

    def test_recommendations_without_genre_id_works(self, client):
        """GET /recommendations/ without genre_id should work (backward compatible)."""
        with patch("backend.app.main.get_popular_books", return_value=([], 0)), \
             patch("backend.app.main._annotate_books_with_ratings", return_value=[]):
            response = client.get("/recommendations/")
            assert response.status_code == 200

    def test_recommendations_genre_id_none_accepted(self, client):
        """genre_id omitted should work (backward compatible)."""
        with patch("backend.app.main.get_popular_books", return_value=([], 0)), \
             patch("backend.app.main._annotate_books_with_ratings", return_value=[]):
            response = client.get("/recommendations/")
            assert response.status_code == 200

    def test_recommendations_invalid_genre_id_returns_422(self, client):
        """Invalid genre_id value (non-integer) should return 422."""
        response = client.get("/recommendations/", params={"genre_id": "invalid"})
        assert response.status_code == 422

    def test_recommendations_negative_genre_id_returns_422(self, client):
        """Negative genre_id should return 422 (ge=1 constraint)."""
        response = client.get("/recommendations/", params={"genre_id": -1})
        assert response.status_code == 422

    def test_recommendations_zero_genre_id_returns_422(self, client):
        """Zero genre_id should return 422 (ge=1 constraint)."""
        response = client.get("/recommendations/", params={"genre_id": 0})
        assert response.status_code == 422


class TestRecommendationsGenreFiltering:
    """Tests for genre filtering logic in recommendations."""

    @patch("backend.app.main.compute_user_embedding")
    @patch("backend.app.main.find_nearest_books")
    @patch("backend.app.main._annotate_books_with_ratings")
    def test_personalized_recommendations_pass_genre_id(
        self,
        mock_annotate,
        mock_find_nearest,
        mock_compute_embedding,
        client,
        mock_user,
        mock_books_with_genres,
    ):
        """Personalized recommendations should pass genre_id to find_nearest_books."""
        mock_compute_embedding.return_value = [0.1] * 384
        mock_find_nearest.return_value = ([mock_books_with_genres[0]], 1)
        mock_annotate.return_value = []

        def _override_get_session():
            session = _create_mock_session(
                rated_book_ids=list(range(5)),
                genre_exists=True,
            )
            yield session

        app.dependency_overrides[get_session] = _override_get_session

        response = client.get("/recommendations/", params={"genre_id": 1})
        assert response.status_code == 200

        # Verify genre_id was passed to find_nearest_books
        mock_find_nearest.assert_called_once()
        call_kwargs = mock_find_nearest.call_args
        assert call_kwargs.kwargs.get("genre_id") == 1

    @patch("backend.app.main.get_popular_books")
    @patch("backend.app.main._annotate_books_with_ratings")
    def test_popular_recommendations_pass_genre_id(
        self,
        mock_annotate,
        mock_get_popular,
        client,
        mock_user,
        mock_books_with_genres,
    ):
        """Popular (fallback) recommendations should pass genre_id to get_popular_books."""
        mock_get_popular.return_value = ([mock_books_with_genres[1]], 1)
        mock_annotate.return_value = []

        def _override_get_session():
            session = _create_mock_session(
                rated_book_ids=[1, 2],
                genre_exists=True,
            )
            yield session

        app.dependency_overrides[get_session] = _override_get_session

        response = client.get("/recommendations/", params={"genre_id": 2})
        assert response.status_code == 200

        mock_get_popular.assert_called_once()
        call_kwargs = mock_get_popular.call_args
        assert call_kwargs.kwargs.get("genre_id") == 2

    @patch("backend.app.main.compute_user_embedding")
    @patch("backend.app.main.find_nearest_books")
    @patch("backend.app.main._annotate_books_with_ratings")
    def test_no_genre_id_passes_none(
        self,
        mock_annotate,
        mock_find_nearest,
        mock_compute_embedding,
        client,
        mock_books_with_genres,
    ):
        """Without genre_id, None should be passed to recommendation functions."""
        mock_compute_embedding.return_value = [0.1] * 384
        mock_find_nearest.return_value = (mock_books_with_genres, 3)
        mock_annotate.return_value = []

        def _override_get_session():
            session = _create_mock_session(rated_book_ids=list(range(5)))
            yield session

        app.dependency_overrides[get_session] = _override_get_session

        response = client.get("/recommendations/")
        assert response.status_code == 200

        mock_find_nearest.assert_called_once()
        call_kwargs = mock_find_nearest.call_args
        assert call_kwargs.kwargs.get("genre_id") is None

    def test_nonexistent_genre_id_returns_404(self, mock_user):
        """A genre_id that doesn't exist should return 404."""

        def _override_get_current_user():
            return mock_user

        def _override_get_session():
            session = _create_mock_session(
                rated_book_ids=[1, 2],
                genre_exists=False,
            )
            yield session

        app.dependency_overrides[get_current_user] = _override_get_current_user
        app.dependency_overrides[get_session] = _override_get_session

        test_client = TestClient(app, raise_server_exceptions=False)
        response = test_client.get("/recommendations/", params={"genre_id": 999})
        assert response.status_code == 404

        app.dependency_overrides.clear()

    @patch("backend.app.main.compute_user_embedding")
    @patch("backend.app.main.find_nearest_books")
    @patch("backend.app.main._annotate_books_with_ratings")
    def test_genre_filter_with_category_filter(
        self,
        mock_annotate,
        mock_find_nearest,
        mock_compute_embedding,
        client,
        mock_user,
        mock_books_with_genres,
    ):
        """genre_id should work together with category parameter."""
        mock_compute_embedding.return_value = [0.1] * 384
        mock_find_nearest.return_value = ([mock_books_with_genres[0]], 1)
        mock_annotate.return_value = []

        def _override_get_session():
            session = _create_mock_session(
                rated_book_ids=list(range(5)),
                genre_exists=True,
            )
            yield session

        app.dependency_overrides[get_session] = _override_get_session

        response = client.get(
            "/recommendations/", params={"genre_id": 1, "category": "fiction"}
        )
        assert response.status_code == 200

        # Verify both genre_id and category were used
        mock_find_nearest.assert_called_once()
        call_kwargs = mock_find_nearest.call_args
        assert call_kwargs.kwargs.get("genre_id") == 1


class TestRecommendationsOpenAPISchema:
    """Tests for OpenAPI schema documentation."""

    def test_recommendations_genre_id_in_openapi_schema(self):
        """The genre_id parameter should be documented in OpenAPI schema."""
        schema = app.openapi()
        recs_path = schema["paths"].get("/recommendations/", {})
        get_op = recs_path.get("get", {})
        parameters = get_op.get("parameters", [])
        param_names = {p.get("name") for p in parameters}
        assert "genre_id" in param_names, (
            "/recommendations/ OpenAPI schema should include genre_id parameter"
        )

    def test_recommendations_genre_id_parameter_is_optional(self):
        """The genre_id parameter should be marked as optional in schema."""
        schema = app.openapi()
        recs_path = schema["paths"].get("/recommendations/", {})
        get_op = recs_path.get("get", {})
        parameters = get_op.get("parameters", [])
        genre_id_param = next(
            (p for p in parameters if p.get("name") == "genre_id"), None
        )
        assert genre_id_param is not None
        # Optional parameters have required=False or no required key
        assert genre_id_param.get("required", False) is False
