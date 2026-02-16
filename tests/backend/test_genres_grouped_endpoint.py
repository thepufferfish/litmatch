"""Unit tests for the GET /genres/grouped endpoint.

Verifies that:
1. The endpoint returns genres grouped by fiction/nonfiction/unknown categories
2. Fiction and Non-Fiction genres are excluded from subgenre lists
3. Genres with no books go to unknown category
4. Genres appearing in both categories use majority voting
5. Response structure matches GroupedGenresResponse model
"""

import os

# Ensure required env vars are set before importing config.
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-unit-tests-only")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")

from collections import namedtuple
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app, get_session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Represents a row returned by the aggregation query
GenreRow = namedtuple("GenreRow", ["id", "name", "fiction_count", "nonfiction_count"])


def _create_mock_session_for_grouped_genres(rows: list[GenreRow]):
    """Build a mock session that returns aggregation rows."""
    session = MagicMock()
    result = MagicMock()
    result.all.return_value = rows
    session.exec.return_value = result
    return session


@pytest.fixture
def sample_rows() -> list[GenreRow]:
    """Aggregated genre rows for testing (Fiction/Non-Fiction already excluded)."""
    return [
        GenreRow(id=3, name="Mystery", fiction_count=2, nonfiction_count=0),
        GenreRow(id=4, name="Biography", fiction_count=0, nonfiction_count=3),
        GenreRow(id=5, name="Science Fiction", fiction_count=4, nonfiction_count=0),
        GenreRow(id=6, name="History", fiction_count=0, nonfiction_count=2),
        GenreRow(id=7, name="Orphan Genre", fiction_count=0, nonfiction_count=0),
        GenreRow(id=8, name="Mixed Genre", fiction_count=2, nonfiction_count=1),
    ]


@pytest.fixture
def client(sample_rows: list[GenreRow]):
    """TestClient with mocked session for grouped genres."""

    def _override_get_session():
        session = _create_mock_session_for_grouped_genres(sample_rows)
        yield session

    app.dependency_overrides[get_session] = _override_get_session
    test_client = TestClient(app, raise_server_exceptions=False)
    yield test_client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests: GET /genres/grouped endpoint
# ---------------------------------------------------------------------------


class TestGenresGroupedEndpoint:
    """Tests for the GET /genres/grouped endpoint."""

    def test_endpoint_exists(self):
        """The /genres/grouped endpoint should be registered."""
        schema = app.openapi()
        assert "/genres/grouped" in schema["paths"], (
            "/genres/grouped endpoint should be registered in the app"
        )

    def test_grouped_genres_returns_200(self, client):
        """GET /genres/grouped should return 200."""
        response = client.get("/genres/grouped")
        assert response.status_code == 200

    def test_grouped_genres_response_structure(self, client):
        """Response should have fiction, nonfiction, and unknown lists."""
        response = client.get("/genres/grouped")
        assert response.status_code == 200
        data = response.json()
        assert "fiction" in data
        assert "nonfiction" in data
        assert "unknown" in data
        assert isinstance(data["fiction"], list)
        assert isinstance(data["nonfiction"], list)
        assert isinstance(data["unknown"], list)

    def test_genre_objects_have_id_and_name(self, client):
        """Each genre object should have id and name fields."""
        response = client.get("/genres/grouped")
        assert response.status_code == 200
        data = response.json()

        for category in ["fiction", "nonfiction", "unknown"]:
            for genre in data[category]:
                assert "id" in genre
                assert "name" in genre
                assert isinstance(genre["id"], int)
                assert isinstance(genre["name"], str)

    def test_fiction_and_nonfiction_genres_excluded(self, client):
        """Fiction and Non-Fiction genres should not appear in any list.

        The SQL query filters them out via WHERE clause, so the mock data
        should not include them. This test verifies the response is clean.
        """
        response = client.get("/genres/grouped")
        assert response.status_code == 200
        data = response.json()

        all_genres = (
            data["fiction"] + data["nonfiction"] + data["unknown"]
        )
        genre_names = [g["name"] for g in all_genres]

        assert "Fiction" not in genre_names
        assert "Non-Fiction" not in genre_names

    def test_fiction_genres_in_fiction_category(self, client):
        """Genres associated only with fiction books should be in fiction list."""
        response = client.get("/genres/grouped")
        assert response.status_code == 200
        data = response.json()

        fiction_names = [g["name"] for g in data["fiction"]]
        assert "Mystery" in fiction_names
        assert "Science Fiction" in fiction_names

    def test_nonfiction_genres_in_nonfiction_category(self, client):
        """Genres associated only with nonfiction books should be in nonfiction list."""
        response = client.get("/genres/grouped")
        assert response.status_code == 200
        data = response.json()

        nonfiction_names = [g["name"] for g in data["nonfiction"]]
        assert "Biography" in nonfiction_names
        assert "History" in nonfiction_names

    def test_genres_with_no_books_in_unknown(self, client):
        """Genres with no books should be in unknown category."""
        response = client.get("/genres/grouped")
        assert response.status_code == 200
        data = response.json()

        unknown_names = [g["name"] for g in data["unknown"]]
        assert "Orphan Genre" in unknown_names

    def test_mixed_genre_uses_majority_voting(self, client):
        """Genres in both categories should use majority voting (2 fiction > 1 nonfiction)."""
        response = client.get("/genres/grouped")
        assert response.status_code == 200
        data = response.json()

        fiction_names = [g["name"] for g in data["fiction"]]
        nonfiction_names = [g["name"] for g in data["nonfiction"]]

        assert "Mixed Genre" in fiction_names
        assert "Mixed Genre" not in nonfiction_names

    def test_empty_database_returns_empty_lists(self):
        """When no genres exist, should return empty lists."""
        def _override_get_session():
            session = _create_mock_session_for_grouped_genres([])
            yield session

        app.dependency_overrides[get_session] = _override_get_session
        test_client = TestClient(app, raise_server_exceptions=False)

        response = test_client.get("/genres/grouped")
        assert response.status_code == 200
        data = response.json()
        assert data["fiction"] == []
        assert data["nonfiction"] == []
        assert data["unknown"] == []

        app.dependency_overrides.clear()

    def test_tie_goes_to_fiction(self):
        """When fiction and nonfiction counts are equal, genre goes to fiction."""
        rows = [GenreRow(id=10, name="Tied Genre", fiction_count=3, nonfiction_count=3)]

        def _override_get_session():
            session = _create_mock_session_for_grouped_genres(rows)
            yield session

        app.dependency_overrides[get_session] = _override_get_session
        test_client = TestClient(app, raise_server_exceptions=False)

        response = test_client.get("/genres/grouped")
        assert response.status_code == 200
        data = response.json()

        fiction_names = [g["name"] for g in data["fiction"]]
        assert "Tied Genre" in fiction_names

        app.dependency_overrides.clear()
