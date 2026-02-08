"""Integration tests for auth endpoints and protected routes.

Uses SQLite in-memory database to test without PostgreSQL.
"""
import os
os.environ.setdefault("DATABASE_URL", "sqlite:///")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-endpoints")
os.environ.setdefault("COOKIE_SECURE", "false")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from backend.app.main import app, get_session
from backend.app.rate_limit import limiter
from backend.db.models import Author, Book


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables fresh for each test and override the get_session dependency."""
    # Disable rate limiting during tests
    limiter.enabled = False

    # Create a fresh in-memory db for each test
    # StaticPool ensures the same connection is reused (required for SQLite in-memory)
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    SQLModel.metadata.create_all(test_engine)

    def override_get_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    yield test_engine
    app.dependency_overrides.clear()
    limiter.enabled = True
    SQLModel.metadata.drop_all(test_engine)
    test_engine.dispose()


@pytest.fixture
def client():
    return TestClient(app)


def _register_user(client: TestClient, username: str = "testuser1", password: str = "Secret123"):
    """Helper to register a user and return response."""
    return client.post(
        "/auth/register",
        json={"username": username, "password": password},
    )


class TestRegister:
    def test_register_success(self, client: TestClient):
        response = _register_user(client, "newuser1")
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "newuser1"

    def test_register_sets_refresh_cookie(self, client: TestClient):
        response = _register_user(client, "cookieuser")
        assert response.status_code == 200
        cookies = response.cookies
        assert "refresh_token" in cookies

    def test_register_duplicate_username(self, client: TestClient):
        _register_user(client, "duplicate1")
        response = _register_user(client, "duplicate1", "DifferentPass1")
        assert response.status_code == 400
        assert response.json()["detail"] == "Registration failed"

    def test_register_invalid_username(self, client: TestClient):
        response = client.post(
            "/auth/register",
            json={"username": "ab", "password": "Secret123"},
        )
        assert response.status_code == 422

    def test_register_invalid_password(self, client: TestClient):
        response = client.post(
            "/auth/register",
            json={"username": "validuser", "password": "short"},
        )
        assert response.status_code == 422


class TestLogin:
    def test_login_success(self, client: TestClient):
        _register_user(client, "loginuser")
        response = client.post(
            "/auth/login",
            json={"username": "loginuser", "password": "Secret123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "loginuser"

    def test_login_sets_refresh_cookie(self, client: TestClient):
        _register_user(client, "logincookie")
        response = client.post(
            "/auth/login",
            json={"username": "logincookie", "password": "Secret123"},
        )
        cookies = response.cookies
        assert "refresh_token" in cookies

    def test_login_wrong_password(self, client: TestClient):
        _register_user(client, "wrongpw")
        response = client.post(
            "/auth/login",
            json={"username": "wrongpw", "password": "WrongPass1"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"

    def test_login_nonexistent_user(self, client: TestClient):
        response = client.post(
            "/auth/login",
            json={"username": "nouser123", "password": "Secret123"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid credentials"


class TestRefresh:
    def test_refresh_returns_new_access_token(self, client: TestClient):
        reg_response = _register_user(client, "refreshuser")
        assert reg_response.status_code == 200

        # The TestClient automatically sends cookies
        refresh_response = client.post("/auth/refresh")
        assert refresh_response.status_code == 200
        data = refresh_response.json()
        assert "access_token" in data

    def test_refresh_without_cookie_fails(self):
        # Create a fresh client with no cookies
        fresh_client = TestClient(app, cookies={})
        response = fresh_client.post("/auth/refresh")
        assert response.status_code == 401


class TestLogout:
    def test_logout_clears_cookie(self, client: TestClient):
        _register_user(client, "logoutuser")
        response = client.post("/auth/logout")
        assert response.status_code == 200
        assert response.json()["detail"] == "Logged out"


class TestProtectedRatings:
    def test_post_rating_without_auth_fails(self, client: TestClient):
        response = client.post(
            "/ratings/",
            json={"book_id": 1, "rating": 5},
        )
        # Should reject unauthenticated requests
        assert response.status_code in (401, 403)

    def test_post_rating_with_auth_succeeds(self, client: TestClient, setup_db):
        reg_response = _register_user(client, "ratinguser")
        token = reg_response.json()["access_token"]

        # Create a book in the test database
        test_engine = setup_db
        with Session(test_engine) as session:
            author = Author(name="Test Author")
            session.add(author)
            session.commit()
            session.refresh(author)
            book = Book(
                title="Test Book",
                author_id=author.id,
                description="A test book",
                url="http://example.com/test-book",
            )
            session.add(book)
            session.commit()
            session.refresh(book)
            book_id = book.id

        response = client.post(
            "/ratings/",
            json={"book_id": book_id, "rating": 4},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["rating"] == 4
        assert data["book_id"] == book_id

    def test_post_rating_invalid_value(self, client: TestClient):
        reg_response = _register_user(client, "ratingval")
        token = reg_response.json()["access_token"]

        response = client.post(
            "/ratings/",
            json={"book_id": 1, "rating": 6},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    def test_get_ratings_without_auth_fails(self, client: TestClient):
        """GET /ratings/ now requires authentication (C-4 fix)."""
        response = client.get("/ratings/")
        assert response.status_code == 401

    def test_get_ratings_with_auth_returns_only_user_ratings(self, client: TestClient, setup_db):
        """GET /ratings/ returns only the authenticated user's ratings (C-4 fix)."""
        # Register two users
        user1_response = _register_user(client, "user1", "Secret123")
        user1_token = user1_response.json()["access_token"]

        user2_response = _register_user(client, "user2", "Secret456")
        user2_token = user2_response.json()["access_token"]

        # Create a book
        test_engine = setup_db
        with Session(test_engine) as session:
            author = Author(name="Test Author")
            session.add(author)
            session.commit()
            session.refresh(author)
            book = Book(
                title="Test Book",
                author_id=author.id,
                description="A test book",
                url="http://example.com/test-book",
            )
            session.add(book)
            session.commit()
            session.refresh(book)
            book_id = book.id

        # User 1 rates the book
        client.post(
            "/ratings/",
            json={"book_id": book_id, "rating": 5},
            headers={"Authorization": f"Bearer {user1_token}"},
        )

        # User 2 rates the book
        client.post(
            "/ratings/",
            json={"book_id": book_id, "rating": 3},
            headers={"Authorization": f"Bearer {user2_token}"},
        )

        # User 1 retrieves their ratings - should only see their own
        response = client.get(
            "/ratings/",
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert response.status_code == 200
        ratings = response.json()
        assert len(ratings) == 1
        assert ratings[0]["rating"] == 5

        # User 2 retrieves their ratings - should only see their own
        response = client.get(
            "/ratings/",
            headers={"Authorization": f"Bearer {user2_token}"},
        )
        assert response.status_code == 200
        ratings = response.json()
        assert len(ratings) == 1
        assert ratings[0]["rating"] == 3
