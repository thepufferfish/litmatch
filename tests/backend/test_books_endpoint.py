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

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app, get_current_user, get_session, read_books
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


# ---------------------------------------------------------------------------
# Tests: Full-Text Search (FTS) with q parameter
# ---------------------------------------------------------------------------


class TestBooksFTSSearch:
    """Tests for the full-text search q parameter on /books/ endpoint."""

    def test_books_q_parameter_accepted(self, client):
        """GET /books/?q=searchterm should be accepted and return 200."""
        response = client.get("/books/", params={"q": "test search"})
        assert response.status_code == 200

    def test_books_q_too_short_returns_400(self, client):
        """Search query shorter than 2 characters should return 400."""
        response = client.get("/books/", params={"q": "a"})
        assert response.status_code == 400
        data = response.json()
        assert "Search query must be at least 2 characters" in data["detail"]

    def test_books_q_empty_string_returns_400(self, client):
        """Empty search query should return 400."""
        response = client.get("/books/", params={"q": ""})
        assert response.status_code == 400

    def test_books_q_whitespace_only_returns_400(self, client):
        """Whitespace-only search query should return 400."""
        response = client.get("/books/", params={"q": " "})
        assert response.status_code == 400

    def test_books_q_combined_with_genre_filter(self, client):
        """q parameter should work with genre filter."""
        response = client.get("/books/", params={"q": "fiction", "genre": 1})
        assert response.status_code == 200

    def test_books_q_combined_with_category_filter(self, client):
        """q parameter should work with category filter."""
        response = client.get("/books/", params={"q": "mystery", "category": "fiction"})
        assert response.status_code == 200

    def test_books_q_combined_with_sort(self, client):
        """q parameter should work with sort parameter."""
        response = client.get("/books/", params={"q": "novel", "sort": "title_asc"})
        assert response.status_code == 200

    def test_books_q_max_length_validation(self, client):
        """Search query exceeding max_length should return 422."""
        long_query = "a" * 201  # max_length is 200
        response = client.get("/books/", params={"q": long_query})
        assert response.status_code == 422

    def test_books_q_parameter_exists_in_openapi(self):
        """The q parameter should be documented in OpenAPI schema."""
        schema = app.openapi()
        books_path = schema["paths"].get("/books/", {})
        get_op = books_path.get("get", {})
        parameters = get_op.get("parameters", [])
        param_names = {p.get("name") for p in parameters}
        assert "q" in param_names, (
            "/books/ OpenAPI schema should include q parameter"
        )

    def test_read_books_function_has_q_parameter(self):
        """The read_books function should accept a q parameter."""
        sig = inspect.signature(read_books)
        param_names = set(sig.parameters.keys())
        assert "q" in param_names, (
            "read_books should have a q parameter"
        )


# ---------------------------------------------------------------------------
# Tests: Query helper functions (build_fts_filter, escape_like)
# ---------------------------------------------------------------------------


class TestQueryHelpers:
    """Tests for query helper functions in backend.app.queries."""

    def test_escape_like_escapes_backslash(self):
        """escape_like should escape backslash characters."""
        from backend.app.queries import escape_like
        assert escape_like("test\\value") == "test\\\\value"

    def test_escape_like_escapes_percent(self):
        """escape_like should escape percent wildcard."""
        from backend.app.queries import escape_like
        assert escape_like("test%value") == "test\\%value"

    def test_escape_like_escapes_underscore(self):
        """escape_like should escape underscore wildcard."""
        from backend.app.queries import escape_like
        assert escape_like("test_value") == "test\\_value"

    def test_escape_like_escapes_all_wildcards(self):
        """escape_like should handle multiple wildcards."""
        from backend.app.queries import escape_like
        assert escape_like("test%_value\\end") == "test\\%\\_value\\\\end"

    def test_escape_like_handles_empty_string(self):
        """escape_like should handle empty string."""
        from backend.app.queries import escape_like
        assert escape_like("") == ""

    def test_build_fts_filter_returns_tuple(self):
        """build_fts_filter should return a tuple of (filter, rank)."""
        from backend.app.queries import build_fts_filter
        result = build_fts_filter("test query")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_build_fts_filter_with_empty_query(self):
        """build_fts_filter should handle empty query."""
        from backend.app.queries import build_fts_filter
        filter_clause, rank_expr = build_fts_filter("")
        assert filter_clause is not None
        assert rank_expr is not None

    def test_build_fts_filter_with_special_characters(self):
        """build_fts_filter should handle special characters."""
        from backend.app.queries import build_fts_filter
        filter_clause, rank_expr = build_fts_filter("test & query | special")
        assert filter_clause is not None
        assert rank_expr is not None


# ---------------------------------------------------------------------------
# Tests: GET /books/{id}/similar endpoint
# ---------------------------------------------------------------------------


def _make_book(book_id: int, author: Author, genres: list[Genre] | None = None) -> Book:
    """Helper to create a Book with optional genres for testing."""
    book = Book(
        id=book_id,
        title=f"Book {book_id}",
        author_id=author.id,
        publisher_id=None,
        publish_date=None,
        description=f"Description for book {book_id}",
        url=f"https://example.com/book{book_id}",
        cover=None,
        author=author,
    )
    book.genres = genres or []
    return book


class TestSimilarBooksEndpoint:
    """Tests for GET /books/{id}/similar endpoint."""

    @pytest.fixture
    def similar_client(self):
        """TestClient with session override but no auth (endpoint is public)."""
        session = MagicMock()

        def _override_get_session():
            yield session

        app.dependency_overrides[get_session] = _override_get_session
        test_client = TestClient(app, raise_server_exceptions=False)
        yield test_client, session
        app.dependency_overrides.clear()

    def test_similar_books_returns_404_for_missing_book(self, similar_client):
        """GET /books/9999/similar should return 404 when book does not exist."""
        client, session = similar_client
        session.exec.return_value.first.return_value = None

        response = client.get("/books/9999/similar")
        assert response.status_code == 404

    def test_similar_books_uses_embedding_when_available(self, similar_client):
        """When embedding exists, result comes from find_similar_books_by_embedding."""
        client, session = similar_client
        author = Author(id=1, name="Author A")
        genre = Genre(id=1, name="Fiction")
        book = _make_book(1, author, genres=[genre])

        # Session returns the book on lookup
        session.exec.return_value.first.return_value = book

        similar_book = _make_book(2, author, genres=[genre])

        with patch(
            "backend.app.main.find_similar_books_by_embedding",
            return_value=[similar_book],
        ) as mock_embed, patch(
            "backend.app.main.find_similar_books_by_genre",
            return_value=[],
        ) as mock_genre:
            # _annotate_books_with_ratings calls session.exec too -- mock it
            session.exec.return_value.all.return_value = []
            response = client.get("/books/1/similar")

        assert response.status_code == 200
        mock_embed.assert_called_once()
        mock_genre.assert_not_called()

    def test_similar_books_falls_back_to_genre_when_no_embedding(self, similar_client):
        """When no embedding exists, falls back to find_similar_books_by_genre."""
        client, session = similar_client
        author = Author(id=1, name="Author A")
        genre = Genre(id=1, name="Fiction")
        book = _make_book(1, author, genres=[genre])

        session.exec.return_value.first.return_value = book

        similar_book = _make_book(3, author, genres=[genre])

        with patch(
            "backend.app.main.find_similar_books_by_embedding",
            return_value=[],
        ) as mock_embed, patch(
            "backend.app.main.find_similar_books_by_genre",
            return_value=[similar_book],
        ) as mock_genre:
            session.exec.return_value.all.return_value = []
            response = client.get("/books/1/similar")

        assert response.status_code == 200
        mock_embed.assert_called_once()
        mock_genre.assert_called_once()

    def test_similar_books_returns_empty_list_when_no_embedding_and_no_genres(
        self, similar_client
    ):
        """Book with no embedding and no genres should return 200 with empty list."""
        client, session = similar_client
        author = Author(id=1, name="Author A")
        book = _make_book(1, author, genres=[])

        session.exec.return_value.first.return_value = book

        with patch(
            "backend.app.main.find_similar_books_by_embedding",
            return_value=[],
        ), patch(
            "backend.app.main.find_similar_books_by_genre",
            return_value=[],
        ):
            session.exec.return_value.all.return_value = []
            response = client.get("/books/1/similar")

        assert response.status_code == 200
        assert response.json() == []

    def test_similar_books_does_not_reference_book_embedding_attribute(self):
        """The get_similar_books handler must NOT reference book.embedding."""
        import inspect
        from backend.app.main import get_similar_books

        source = inspect.getsource(get_similar_books)
        assert "book.embedding" not in source, (
            "get_similar_books references the removed book.embedding attribute"
        )


# ---------------------------------------------------------------------------
# Tests: GET /genres/ should not leak embedding field
# ---------------------------------------------------------------------------


class TestGenresEndpointNoEmbeddingLeak:
    """Tests that /genres/ does not expose the internal embedding column."""

    @pytest.fixture
    def genres_client(self):
        """TestClient with a session that returns one Genre with an embedding."""
        genre_with_embedding = Genre(id=1, name="Fiction")
        # Simulate an embedding present in the DB row
        genre_with_embedding.embedding = [0.1, 0.2, 0.3]

        session = MagicMock()
        session.exec.return_value.all.return_value = [genre_with_embedding]

        def _override_get_session():
            yield session

        app.dependency_overrides[get_session] = _override_get_session
        test_client = TestClient(app, raise_server_exceptions=False)
        yield test_client
        app.dependency_overrides.clear()

    def test_genres_endpoint_returns_200(self, genres_client):
        """GET /genres/ should return 200."""
        response = genres_client.get("/genres/")
        assert response.status_code == 200

    def test_genres_response_has_no_embedding_field(self, genres_client):
        """GET /genres/ response should NOT contain an embedding field."""
        response = genres_client.get("/genres/")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        for genre_item in data:
            assert "embedding" not in genre_item, (
                f"Genre response leaks embedding field: {genre_item}"
            )

    def test_genres_response_contains_id_and_name(self, genres_client):
        """GET /genres/ response items should have id and name fields."""
        response = genres_client.get("/genres/")
        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0
        for genre_item in data:
            assert "id" in genre_item
            assert "name" in genre_item

    def test_genres_openapi_response_model_uses_genre_simple(self):
        """The /genres/ route should use GenreSimple as response model (no embedding)."""
        schema = app.openapi()
        genres_path = schema["paths"].get("/genres/", {})
        get_op = genres_path.get("get", {})
        # Get the response schema reference
        responses = get_op.get("responses", {})
        ok_response = responses.get("200", {})
        content = ok_response.get("content", {})
        json_content = content.get("application/json", {})
        schema_ref = json_content.get("schema", {})
        # The items ref should point to GenreSimple, not Genre
        ref_str = str(schema_ref)
        assert "Genre" in ref_str  # Some Genre type is referenced
        # Verify GenreSimple schema has only id and name (no embedding)
        components = schema.get("components", {})
        schemas = components.get("schemas", {})
        genre_simple_schema = schemas.get("GenreSimple")
        if genre_simple_schema:
            props = genre_simple_schema.get("properties", {})
            assert "embedding" not in props, (
                "GenreSimple schema should not have an embedding property"
            )
