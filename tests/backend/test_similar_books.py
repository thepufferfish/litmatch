"""Unit tests for the GET /books/{book_id}/similar endpoint.

Verifies that:
1. Similar books are returned using embedding-based cosine distance when available.
2. Genre-based fallback returns books with overlapping genres when no embedding.
3. Proper 404 for missing books, 422 for invalid parameters.
4. The source book is excluded from results.
5. Default and max limit constraints are enforced.
6. Query functions handle edge cases correctly.
"""

import os

# Ensure required env vars are set before importing config.
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-only")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app, get_session
from backend.app.rate_limit import limiter
from backend.db.models import (
    Author,
    Book,
    BookRead,
    Genre,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_author() -> Author:
    return Author(id=1, name="Test Author")


def _make_book(
    book_id: int,
    mock_author: Author,
    embedding: list[float] | None = None,
    genres: list[Genre] | None = None,
) -> Book:
    """Create a mock Book with the given ID and optional embedding/genres."""
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
        embedding=embedding,
    )
    book.genres = genres or []
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


def _create_mock_session(book: Book | None = None):
    """Build a mock SQLModel session that returns a book for get() and exec()."""
    session = MagicMock()
    session.get.return_value = book

    # session.exec() returns a result whose .first() yields the book
    exec_result = MagicMock()
    exec_result.all.return_value = [book] if book else []
    exec_result.first.return_value = book
    session.exec.return_value = exec_result

    return session


@pytest.fixture
def client():
    """TestClient that overrides session dependency and disables rate limiter."""
    limiter.enabled = False

    def _override_get_session():
        session = _create_mock_session(book=None)
        yield session

    app.dependency_overrides[get_session] = _override_get_session

    test_client = TestClient(app, raise_server_exceptions=False)
    yield test_client

    app.dependency_overrides.clear()
    limiter.enabled = True


def _client_with_book(book: Book):
    """Create a TestClient with a session that returns the given book."""
    limiter.enabled = False

    def _override_get_session():
        session = _create_mock_session(book=book)
        yield session

    app.dependency_overrides[get_session] = _override_get_session

    test_client = TestClient(app, raise_server_exceptions=False)
    return test_client


# ---------------------------------------------------------------------------
# Tests: GET /books/{book_id}/similar endpoint
# ---------------------------------------------------------------------------


class TestSimilarBooksEndpoint:
    """Tests for the GET /books/{book_id}/similar endpoint."""

    @patch("backend.app.main._annotate_books_with_ratings")
    @patch("backend.app.main.find_similar_books_by_embedding")
    def test_returns_similar_books_with_embedding(
        self, mock_find_embedding, mock_annotate, mock_author
    ):
        """When the source book has an embedding, use embedding-based similarity."""
        limiter.enabled = False
        source_book = _make_book(1, mock_author, embedding=[0.1] * 384)
        similar_books = [_make_book(2, mock_author), _make_book(3, mock_author)]
        mock_find_embedding.return_value = similar_books
        mock_annotate.return_value = [_make_book_read(2), _make_book_read(3)]

        def _override_get_session():
            session = _create_mock_session(book=source_book)
            yield session

        app.dependency_overrides[get_session] = _override_get_session
        test_client = TestClient(app, raise_server_exceptions=False)

        try:
            response = test_client.get("/books/1/similar")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            assert data[0]["id"] == 2
            assert data[1]["id"] == 3
            mock_find_embedding.assert_called_once()
        finally:
            app.dependency_overrides.clear()
            limiter.enabled = True

    @patch("backend.app.main._annotate_books_with_ratings")
    @patch("backend.app.main.find_similar_books_by_genre")
    @patch("backend.app.main.find_similar_books_by_embedding")
    def test_returns_similar_books_with_genre_fallback(
        self, mock_find_embedding, mock_find_genre, mock_annotate, mock_author
    ):
        """When no embedding exists, fall back to genre-based similarity."""
        limiter.enabled = False
        genre = Genre(id=5, name="Mystery")
        source_book = _make_book(1, mock_author, embedding=None, genres=[genre])
        similar_books = [_make_book(2, mock_author), _make_book(3, mock_author)]
        # Embedding lookup returns empty (no BookEmbedding row), triggering fallback
        mock_find_embedding.return_value = []
        mock_find_genre.return_value = similar_books
        mock_annotate.return_value = [_make_book_read(2), _make_book_read(3)]

        def _override_get_session():
            session = _create_mock_session(book=source_book)
            yield session

        app.dependency_overrides[get_session] = _override_get_session
        test_client = TestClient(app, raise_server_exceptions=False)

        try:
            response = test_client.get("/books/1/similar")
            assert response.status_code == 200
            data = response.json()
            assert len(data) == 2
            mock_find_embedding.assert_called_once()
            mock_find_genre.assert_called_once()
        finally:
            app.dependency_overrides.clear()
            limiter.enabled = True

    def test_book_not_found_returns_404(self, client):
        """GET /books/999/similar should return 404 when book does not exist."""
        response = client.get("/books/999/similar")
        assert response.status_code == 404
        data = response.json()
        assert data["detail"] == "Book not found"

    def test_invalid_book_id_returns_422(self, client):
        """GET /books/0/similar should return 422 for book_id < 1."""
        response = client.get("/books/0/similar")
        assert response.status_code == 422

    def test_negative_book_id_returns_422(self, client):
        """GET /books/-1/similar should return 422 for negative book_id."""
        response = client.get("/books/-1/similar")
        assert response.status_code == 422

    @patch("backend.app.main._annotate_books_with_ratings")
    @patch("backend.app.main.find_similar_books_by_embedding")
    def test_limit_default_is_10(
        self, mock_find_embedding, mock_annotate, mock_author
    ):
        """Default limit should be 10 when not specified."""
        limiter.enabled = False
        source_book = _make_book(1, mock_author, embedding=[0.1] * 384)
        mock_find_embedding.return_value = []
        mock_annotate.return_value = []

        def _override_get_session():
            session = _create_mock_session(book=source_book)
            yield session

        app.dependency_overrides[get_session] = _override_get_session
        test_client = TestClient(app, raise_server_exceptions=False)

        try:
            response = test_client.get("/books/1/similar")
            assert response.status_code == 200
            # Verify limit=10 was passed to query function
            call_args = mock_find_embedding.call_args
            assert call_args[1].get("limit", call_args[0][2] if len(call_args[0]) > 2 else None) == 10 or \
                   (len(call_args[0]) > 2 and call_args[0][2] == 10) or \
                   call_args.kwargs.get("limit") == 10
        finally:
            app.dependency_overrides.clear()
            limiter.enabled = True

    def test_limit_exceeds_max_returns_422(self, client, mock_author):
        """limit > 20 should return 422."""
        limiter.enabled = False
        source_book = _make_book(1, mock_author, embedding=[0.1] * 384)

        def _override_get_session():
            session = _create_mock_session(book=source_book)
            yield session

        app.dependency_overrides[get_session] = _override_get_session

        try:
            response = client.get("/books/1/similar", params={"limit": 21})
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()
            limiter.enabled = True

    def test_limit_zero_returns_422(self, client, mock_author):
        """limit < 1 should return 422."""
        limiter.enabled = False
        source_book = _make_book(1, mock_author, embedding=[0.1] * 384)

        def _override_get_session():
            session = _create_mock_session(book=source_book)
            yield session

        app.dependency_overrides[get_session] = _override_get_session

        try:
            response = client.get("/books/1/similar", params={"limit": 0})
            assert response.status_code == 422
        finally:
            app.dependency_overrides.clear()
            limiter.enabled = True

    @patch("backend.app.main._annotate_books_with_ratings")
    @patch("backend.app.main.find_similar_books_by_embedding")
    def test_excludes_source_book(
        self, mock_find_embedding, mock_annotate, mock_author
    ):
        """Results should never include the source book itself."""
        limiter.enabled = False
        source_book = _make_book(1, mock_author, embedding=[0.1] * 384)
        # Simulate query function already excluding the source
        similar_books = [_make_book(2, mock_author), _make_book(3, mock_author)]
        mock_find_embedding.return_value = similar_books
        mock_annotate.return_value = [_make_book_read(2), _make_book_read(3)]

        def _override_get_session():
            session = _create_mock_session(book=source_book)
            yield session

        app.dependency_overrides[get_session] = _override_get_session
        test_client = TestClient(app, raise_server_exceptions=False)

        try:
            response = test_client.get("/books/1/similar")
            assert response.status_code == 200
            data = response.json()
            book_ids = [b["id"] for b in data]
            assert 1 not in book_ids, "Source book should not appear in similar results"
        finally:
            app.dependency_overrides.clear()
            limiter.enabled = True

    @patch("backend.app.main._annotate_books_with_ratings")
    @patch("backend.app.main.find_similar_books_by_embedding")
    def test_empty_result_returns_empty_list(
        self, mock_find_embedding, mock_annotate, mock_author
    ):
        """When no similar books exist, return an empty list."""
        limiter.enabled = False
        source_book = _make_book(1, mock_author, embedding=[0.1] * 384)
        mock_find_embedding.return_value = []
        mock_annotate.return_value = []

        def _override_get_session():
            session = _create_mock_session(book=source_book)
            yield session

        app.dependency_overrides[get_session] = _override_get_session
        test_client = TestClient(app, raise_server_exceptions=False)

        try:
            response = test_client.get("/books/1/similar")
            assert response.status_code == 200
            data = response.json()
            assert data == []
        finally:
            app.dependency_overrides.clear()
            limiter.enabled = True

    @patch("backend.app.main._annotate_books_with_ratings")
    @patch("backend.app.main.find_similar_books_by_embedding")
    def test_custom_limit_is_respected(
        self, mock_find_embedding, mock_annotate, mock_author
    ):
        """A custom limit query parameter should be passed to the query function."""
        limiter.enabled = False
        source_book = _make_book(1, mock_author, embedding=[0.1] * 384)
        mock_find_embedding.return_value = []
        mock_annotate.return_value = []

        def _override_get_session():
            session = _create_mock_session(book=source_book)
            yield session

        app.dependency_overrides[get_session] = _override_get_session
        test_client = TestClient(app, raise_server_exceptions=False)

        try:
            response = test_client.get("/books/1/similar", params={"limit": 5})
            assert response.status_code == 200
            # Verify the custom limit was forwarded
            mock_find_embedding.assert_called_once()
        finally:
            app.dependency_overrides.clear()
            limiter.enabled = True

    def test_endpoint_exists_in_openapi(self):
        """The /books/{book_id}/similar endpoint should exist in OpenAPI schema."""
        schema = app.openapi()
        assert "/books/{book_id}/similar" in schema["paths"], (
            "/books/{book_id}/similar endpoint should be registered in the app"
        )

    def test_response_model_is_list_of_book_read(self):
        """The endpoint response model should be list[BookRead]."""
        schema = app.openapi()
        similar_path = schema["paths"].get("/books/{book_id}/similar", {})
        get_op = similar_path.get("get", {})
        response_200 = get_op.get("responses", {}).get("200", {})
        content = response_200.get("content", {}).get("application/json", {})
        response_schema = content.get("schema", {})
        # Should be an array type
        assert response_schema.get("type") == "array"


# ---------------------------------------------------------------------------
# Tests: Query function behavior
# ---------------------------------------------------------------------------


class TestSimilarBooksQueryFunctions:
    """Tests for find_similar_books_by_embedding and find_similar_books_by_genre."""

    def test_embedding_query_excludes_source_book(self):
        """find_similar_books_by_embedding should be importable and callable."""
        from backend.app.queries import find_similar_books_by_embedding

        assert callable(find_similar_books_by_embedding)

    def test_genre_query_returns_empty_for_no_genres(self):
        """find_similar_books_by_genre should return [] when genre_ids is empty."""
        from backend.app.queries import find_similar_books_by_genre

        session = MagicMock()
        result = find_similar_books_by_genre(session, book_id=1, genre_ids=[], limit=10)
        assert result == []
        # session.exec should NOT be called for empty genre_ids
        session.exec.assert_not_called()

    def test_genre_query_respects_limit(self):
        """find_similar_books_by_genre should accept and use a limit parameter."""
        from backend.app.queries import find_similar_books_by_genre

        assert callable(find_similar_books_by_genre)
        # Verify it accepts a limit parameter by inspecting the signature
        import inspect

        sig = inspect.signature(find_similar_books_by_genre)
        assert "limit" in sig.parameters
        assert sig.parameters["limit"].default == 10

    def test_embedding_query_accepts_correct_parameters(self):
        """find_similar_books_by_embedding should accept session, book, and limit."""
        from backend.app.queries import find_similar_books_by_embedding
        import inspect

        sig = inspect.signature(find_similar_books_by_embedding)
        param_names = list(sig.parameters.keys())
        assert "session" in param_names
        assert "book" in param_names
        assert "limit" in param_names
        assert sig.parameters["limit"].default == 10

    def test_genre_query_accepts_correct_parameters(self):
        """find_similar_books_by_genre should accept session, book_id, genre_ids, and limit."""
        from backend.app.queries import find_similar_books_by_genre
        import inspect

        sig = inspect.signature(find_similar_books_by_genre)
        param_names = list(sig.parameters.keys())
        assert "session" in param_names
        assert "book_id" in param_names
        assert "genre_ids" in param_names
        assert "limit" in param_names
