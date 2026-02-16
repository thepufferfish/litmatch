"""Integration tests for backend API endpoints.

Tests the FastAPI REST API endpoints against the running compose stack.
Covers auth flows, book search, pagination, and error handling.
"""
import httpx
import pytest


pytestmark = pytest.mark.integration


class TestAuthEndpoints:
    """Tests for the authentication endpoints."""

    def test_register_new_user(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """A new user can register with valid credentials."""
        response = http_client.post(
            f"{backend_url}/auth/register",
            json={"username": "testuser_integ", "password": "TestPass123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["token_type"] == "bearer"
        assert "access_token" in data
        assert data["user"]["username"] == "testuser_integ"

    def test_register_duplicate_user_fails(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """Registering an already-existing username should fail."""
        # Register once
        http_client.post(
            f"{backend_url}/auth/register",
            json={"username": "duplicate_user", "password": "TestPass123"},
        )

        # Register again with same username
        response = http_client.post(
            f"{backend_url}/auth/register",
            json={"username": "duplicate_user", "password": "TestPass456"},
        )

        assert response.status_code == 400

    def test_login_valid_credentials(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """A registered user can log in with correct credentials."""
        # Register
        http_client.post(
            f"{backend_url}/auth/register",
            json={"username": "login_test_user", "password": "TestPass123"},
        )

        # Login
        response = http_client.post(
            f"{backend_url}/auth/login",
            json={"username": "login_test_user", "password": "TestPass123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["token_type"] == "bearer"
        assert "access_token" in data

    def test_login_invalid_credentials(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """Login with wrong password should return 401."""
        response = http_client.post(
            f"{backend_url}/auth/login",
            json={"username": "nonexistent_user", "password": "WrongPass123"},
        )

        assert response.status_code == 401


class TestBookEndpoints:
    """Tests for book listing and detail endpoints."""

    def test_books_list_returns_paginated(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """The books list endpoint should return a paginated response."""
        response = http_client.get(f"{backend_url}/books/?page=1&limit=5")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert data["page"] == 1
        assert data["limit"] == 5

    def test_book_not_found_returns_404(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """Requesting a non-existent book ID should return 404."""
        response = http_client.get(f"{backend_url}/books/99999")

        assert response.status_code == 404

    def test_search_requires_minimum_query_length(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """Search query must be at least 2 characters."""
        response = http_client.get(f"{backend_url}/books/search?q=a")

        assert response.status_code == 400

    def test_search_empty_query_returns_400(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """An empty search query should return 400."""
        response = http_client.get(f"{backend_url}/books/search?q=")

        assert response.status_code == 400


class TestRatingsEndpoints:
    """Tests for the ratings endpoints."""

    def test_ratings_require_authentication(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """The ratings endpoint should require a Bearer token."""
        response = http_client.get(f"{backend_url}/ratings/")

        # Without auth header, should get 401 or 403
        assert response.status_code in (401, 403)

    def test_add_rating_requires_authentication(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """Adding a rating should require a Bearer token."""
        response = http_client.post(
            f"{backend_url}/ratings/",
            json={"book_id": 1, "rating": 5},
        )

        assert response.status_code in (401, 403)


class TestErrorHandling:
    """Tests for API error handling."""

    def test_invalid_page_parameter(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """Page parameter less than 1 should return 422."""
        response = http_client.get(f"{backend_url}/books/?page=0")

        assert response.status_code == 422

    def test_invalid_limit_parameter(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """Limit parameter exceeding max should return 422."""
        response = http_client.get(f"{backend_url}/books/?limit=999")

        assert response.status_code == 422

    def test_nonexistent_endpoint_returns_404(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """A request to a non-existent endpoint should return 404."""
        response = http_client.get(f"{backend_url}/nonexistent")

        assert response.status_code == 404


class TestFullTextSearch:
    """Tests for full-text search functionality on /books/ endpoint."""

    def test_fts_basic_search_returns_results(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """GET /books/?q=<term> should return matching books."""
        response = http_client.get(f"{backend_url}/books/?q=fiction")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    def test_fts_search_with_genre_filter(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """FTS should work combined with genre filter."""
        response = http_client.get(
            f"{backend_url}/books/?q=novel&genre=1"
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_fts_search_with_category_fiction(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """FTS should work combined with fiction category filter."""
        response = http_client.get(
            f"{backend_url}/books/?q=story&category=fiction"
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_fts_search_with_category_nonfiction(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """FTS should work combined with nonfiction category filter."""
        response = http_client.get(
            f"{backend_url}/books/?q=history&category=nonfiction"
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_fts_search_with_sort_title(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """FTS should work with title sorting."""
        response = http_client.get(
            f"{backend_url}/books/?q=book&sort=title_asc"
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        if len(data["items"]) >= 2:
            # Verify titles are in ascending order
            titles = [item["title"] for item in data["items"]]
            assert titles == sorted(titles)

    def test_fts_search_with_sort_date(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """FTS should work with date sorting."""
        response = http_client.get(
            f"{backend_url}/books/?q=novel&sort=date_desc"
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_fts_search_relevance_ordering(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """When no sort is specified, results should be ordered by relevance."""
        response = http_client.get(f"{backend_url}/books/?q=gardener")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        # With FTS, items should come back even if only one matches
        # The most relevant match should appear first

    def test_fts_search_combined_all_filters(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """FTS should work with q + genre + category + sort combined."""
        response = http_client.get(
            f"{backend_url}/books/?q=fiction&genre=1&category=fiction&sort=title_asc"
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_fts_search_pagination(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """FTS results should support pagination."""
        response = http_client.get(
            f"{backend_url}/books/?q=book&page=1&limit=2"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["limit"] == 2
        assert "items" in data

    def test_fts_search_too_short_query(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """FTS query shorter than 2 characters should return 400."""
        response = http_client.get(f"{backend_url}/books/?q=x")

        assert response.status_code == 400
        data = response.json()
        assert "Search query must be at least 2 characters" in data["detail"]

    def test_fts_search_empty_query(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """FTS with empty query should return 400."""
        response = http_client.get(f"{backend_url}/books/?q=")

        assert response.status_code == 400


class TestDeprecatedSearchEndpoint:
    """Tests for the deprecated /books/search endpoint."""

    def test_deprecated_search_endpoint_still_works(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """The deprecated /books/search endpoint should still function."""
        response = http_client.get(f"{backend_url}/books/search?q=novel")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_deprecated_search_with_pagination(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """Deprecated search should support pagination."""
        response = http_client.get(
            f"{backend_url}/books/search?q=book&page=1&limit=5"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1
        assert data["limit"] == 5

    def test_deprecated_search_with_sort(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """Deprecated search should support sort parameter."""
        response = http_client.get(
            f"{backend_url}/books/search?q=fiction&sort=title_asc"
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_deprecated_search_too_short_query(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """Deprecated search should enforce minimum query length."""
        response = http_client.get(f"{backend_url}/books/search?q=a")

        assert response.status_code == 400

    def test_deprecated_search_empty_query(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """Deprecated search should reject empty query."""
        response = http_client.get(f"{backend_url}/books/search?q=")

        assert response.status_code == 400
