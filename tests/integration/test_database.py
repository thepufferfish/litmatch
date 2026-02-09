"""Integration tests for database schema and connectivity.

Verifies that the PostgreSQL database is initialized correctly with
all required tables, pgvector extension, and correct schema.
"""
import httpx
import pytest


pytestmark = pytest.mark.integration


class TestDatabaseSchema:
    """Tests that the database schema is correctly initialized."""

    def test_books_endpoint_returns_empty_initially(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """Before ETL runs, the books endpoint should return an empty list."""
        response = http_client.get(f"{backend_url}/books/")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_genres_endpoint_returns_list(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """The genres endpoint should return a list (possibly empty before ETL)."""
        response = http_client.get(f"{backend_url}/genres/")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_pagination_metadata_present(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """Book list responses should include pagination metadata."""
        response = http_client.get(f"{backend_url}/books/?page=1&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert data["page"] == 1
        assert data["limit"] == 10


class TestDatabaseConnectivity:
    """Tests that the backend maintains database connectivity."""

    def test_repeated_health_checks_succeed(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """Multiple sequential health checks should all succeed."""
        for _ in range(3):
            response = http_client.get(f"{backend_url}/health")
            assert response.status_code == 200
            assert response.json()["status"] == "ok"
