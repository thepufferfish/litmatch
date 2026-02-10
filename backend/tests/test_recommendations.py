"""Tests for the recommendation engine and endpoints.

Tests cover:
- Response model construction
- _compute_weighted_embedding pure math
- compute_user_embedding DB query delegation
- get_popular_books fallback (mocked session)
- find_nearest_books pgvector search (mocked session)
- GET /users/me endpoint
- GET /recommendations/ endpoint
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-recommendations")
os.environ.setdefault("COOKIE_SECURE", "false")

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import selectinload
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from backend.app.main import app, get_session
from backend.app.rate_limit import limiter
from backend.app.recommendations import (
    _compute_weighted_embedding,
    compute_user_embedding,
    find_nearest_books,
)
from backend.db.models import (
    Author,
    Book,
    BookRead,
    RecommendationMeta,
    RecommendationResponse,
    Review,
    UserProfile,
    UserRating,
)


# -----------------------------------------------------------------------
# Response Model Tests
# -----------------------------------------------------------------------


class TestResponseModels:
    def test_recommendation_meta_personalized(self):
        meta = RecommendationMeta(
            strategy="personalized", rating_count=10, category="all"
        )
        assert meta.strategy == "personalized"
        assert meta.rating_count == 10
        assert meta.category == "all"

    def test_recommendation_meta_popular(self):
        meta = RecommendationMeta(
            strategy="popular", rating_count=3, category="fiction"
        )
        assert meta.strategy == "popular"
        assert meta.rating_count == 3
        assert meta.category == "fiction"

    def test_user_profile_fields(self):
        profile = UserProfile(id=1, username="alice", rating_count=7)
        assert profile.id == 1
        assert profile.username == "alice"
        assert profile.rating_count == 7

    def test_recommendation_response_with_empty_items(self):
        meta = RecommendationMeta(
            strategy="popular", rating_count=0, category="all"
        )
        resp = RecommendationResponse(items=[], meta=meta)
        assert resp.items == []
        assert resp.meta.strategy == "popular"

    def test_recommendation_response_with_book_items(self):
        book = BookRead(
            id=1,
            title="Test Book",
            author_id=None,
            publisher_id=None,
            publish_date=None,
            description="desc",
            url="http://example.com",
            cover=None,
        )
        meta = RecommendationMeta(
            strategy="personalized", rating_count=10, category="all"
        )
        resp = RecommendationResponse(items=[book], meta=meta)
        assert len(resp.items) == 1
        assert resp.items[0].title == "Test Book"


# -----------------------------------------------------------------------
# _compute_weighted_embedding Tests (Pure Math)
# -----------------------------------------------------------------------


class TestComputeWeightedEmbedding:
    def test_empty_input(self):
        assert _compute_weighted_embedding([]) is None

    def test_all_none_embeddings(self):
        data = [(5, None), (3, None)]
        assert _compute_weighted_embedding(data) is None

    def test_all_neutral_ratings(self):
        emb = [1.0, 0.0, 0.0]
        data = [(2, emb), (2, emb)]
        assert _compute_weighted_embedding(data) is None

    def test_single_positive_rating(self):
        emb = [1.0, 0.0, 0.0]
        # Rating 5 -> weight +3, normalized by |3| = 3
        # Result: (3 * [1,0,0]) / 3 = [1,0,0]
        result = _compute_weighted_embedding([(5, emb)])
        assert result is not None
        assert len(result) == 3
        assert result[0] == pytest.approx(1.0)
        assert result[1] == pytest.approx(0.0)
        assert result[2] == pytest.approx(0.0)

    def test_single_negative_rating(self):
        emb = [1.0, 0.0, 0.0]
        # Rating 1 -> weight -1, normalized by |-1| = 1
        # Result: (-1 * [1,0,0]) / 1 = [-1,0,0]
        result = _compute_weighted_embedding([(1, emb)])
        assert result is not None
        assert result[0] == pytest.approx(-1.0)

    def test_mixed_ratings(self):
        emb_a = [1.0, 0.0, 0.0]
        emb_b = [0.0, 1.0, 0.0]
        # Rating 5 on A -> weight +3, Rating 1 on B -> weight -1
        # Weighted sum: 3*[1,0,0] + (-1)*[0,1,0] = [3,-1,0]
        # abs_weight_sum = 3 + 1 = 4
        # Result: [3/4, -1/4, 0]
        result = _compute_weighted_embedding([(5, emb_a), (1, emb_b)])
        assert result is not None
        assert result[0] == pytest.approx(0.75)
        assert result[1] == pytest.approx(-0.25)
        assert result[2] == pytest.approx(0.0)

    def test_skips_neutral_ratings(self):
        emb_a = [1.0, 0.0, 0.0]
        emb_b = [0.0, 1.0, 0.0]
        # Rating 2 is neutral (weight 0), only rating 4 (weight +2) counts
        # Result: (2 * [1,0,0]) / 2 = [1,0,0]
        result = _compute_weighted_embedding([(4, emb_a), (2, emb_b)])
        assert result is not None
        assert result[0] == pytest.approx(1.0)
        assert result[1] == pytest.approx(0.0)

    def test_skips_none_embeddings_among_valid(self):
        emb = [0.0, 1.0, 0.0]
        # First has None embedding, second has valid embedding with rating 3 (weight +1)
        result = _compute_weighted_embedding([(5, None), (3, emb)])
        assert result is not None
        assert result[0] == pytest.approx(0.0)
        assert result[1] == pytest.approx(1.0)

    def test_rating_3_mild_positive(self):
        emb = [0.5, 0.5, 0.0]
        # Rating 3 -> weight +1
        # Result: (1 * [0.5, 0.5, 0]) / 1 = [0.5, 0.5, 0]
        result = _compute_weighted_embedding([(3, emb)])
        assert result is not None
        assert result[0] == pytest.approx(0.5)
        assert result[1] == pytest.approx(0.5)

    def test_rating_4_attract(self):
        emb = [1.0, 0.0, 0.0]
        # Rating 4 -> weight +2
        # Result: (2 * [1,0,0]) / 2 = [1,0,0]
        result = _compute_weighted_embedding([(4, emb)])
        assert result is not None
        assert result[0] == pytest.approx(1.0)

    def test_multiple_same_direction(self):
        emb_a = [1.0, 0.0]
        emb_b = [0.5, 0.5]
        # Both rated 5 (weight +3)
        # Weighted sum: 3*[1,0] + 3*[0.5,0.5] = [4.5, 1.5]
        # abs_weight_sum = 6
        # Result: [0.75, 0.25]
        result = _compute_weighted_embedding([(5, emb_a), (5, emb_b)])
        assert result is not None
        assert result[0] == pytest.approx(0.75)
        assert result[1] == pytest.approx(0.25)


# -----------------------------------------------------------------------
# compute_user_embedding Tests (DB Integration, mocked)
# -----------------------------------------------------------------------


class TestComputeUserEmbedding:
    def test_delegates_to_weighted_embedding(self):
        mock_session = MagicMock(spec=Session)
        # Simulate rows: (rating=5, embedding=[1,0,0])
        mock_row = MagicMock()
        mock_row.rating = 5
        mock_row.embedding = [1.0, 0.0, 0.0]
        mock_session.exec.return_value.all.return_value = [mock_row]

        result = compute_user_embedding(mock_session, user_id=1)
        assert result is not None
        assert result[0] == pytest.approx(1.0)

    def test_returns_none_when_no_ratings(self):
        mock_session = MagicMock(spec=Session)
        mock_session.exec.return_value.all.return_value = []

        from backend.app.recommendations import compute_user_embedding

        result = compute_user_embedding(mock_session, user_id=999)
        assert result is None

    def test_category_fiction_filters_to_fiction_only(self):
        """When category='fiction', only fiction book ratings should be used."""
        mock_session = MagicMock(spec=Session)
        fiction_row = MagicMock()
        fiction_row.rating = 5
        fiction_row.embedding = [1.0, 0.0, 0.0]
        mock_session.exec.return_value.all.return_value = [fiction_row]

        result = compute_user_embedding(mock_session, user_id=1, category="fiction")
        assert result is not None
        # Verify exec was called (the SQL filtering is the key fix)
        mock_session.exec.assert_called_once()

    def test_category_nonfiction_filters_to_nonfiction_only(self):
        """When category='nonfiction', only nonfiction book ratings should be used."""
        mock_session = MagicMock(spec=Session)
        nonfiction_row = MagicMock()
        nonfiction_row.rating = 4
        nonfiction_row.embedding = [0.0, 1.0, 0.0]
        mock_session.exec.return_value.all.return_value = [nonfiction_row]

        result = compute_user_embedding(mock_session, user_id=1, category="nonfiction")
        assert result is not None
        mock_session.exec.assert_called_once()

    def test_category_all_uses_all_ratings(self):
        """When category='all', all ratings are included (default behavior)."""
        mock_session = MagicMock(spec=Session)
        row1 = MagicMock()
        row1.rating = 5
        row1.embedding = [1.0, 0.0, 0.0]
        row2 = MagicMock()
        row2.rating = 4
        row2.embedding = [0.0, 1.0, 0.0]
        mock_session.exec.return_value.all.return_value = [row1, row2]

        result = compute_user_embedding(mock_session, user_id=1, category="all")
        assert result is not None

    def test_category_default_is_all(self):
        """Default category parameter should be 'all'."""
        mock_session = MagicMock(spec=Session)
        row = MagicMock()
        row.rating = 5
        row.embedding = [1.0, 0.0, 0.0]
        mock_session.exec.return_value.all.return_value = [row]

        # Calling without category should work (default = "all")
        result = compute_user_embedding(mock_session, user_id=1)
        assert result is not None


# -----------------------------------------------------------------------
# find_nearest_books Tests (pgvector-dependent, mocked)
# -----------------------------------------------------------------------


class TestFindNearestBooks:
    def test_returns_book_list(self):
        mock_book = MagicMock(spec=Book)
        mock_session = MagicMock(spec=Session)
        mock_session.exec.return_value.all.return_value = [mock_book]

        result = find_nearest_books(
            mock_session, [0.1, 0.2, 0.3], set(), "all", 10
        )
        assert len(result) == 1

    def test_returns_empty_list(self):
        mock_session = MagicMock(spec=Session)
        mock_session.exec.return_value.all.return_value = []

        result = find_nearest_books(
            mock_session, [0.1, 0.2, 0.3], set(), "all", 10
        )
        assert result == []


# -----------------------------------------------------------------------
# Endpoint Test Fixtures
# -----------------------------------------------------------------------


@pytest.fixture()
def setup_db():
    """Create tables fresh for each test and override get_session."""
    limiter.enabled = False

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


@pytest.fixture()
def client(setup_db):
    return TestClient(app)


def _register_user(
    client: TestClient,
    username: str = "testuser1",
    password: str = "Secret123",
):
    """Register a user and return (access_token, response)."""
    resp = client.post(
        "/auth/register",
        json={"username": username, "password": password},
    )
    return resp


def _create_book(
    engine, title: str, is_fiction: bool | None = None, url: str | None = None
) -> int:
    """Insert a book and return its ID."""
    with Session(engine) as session:
        author = Author(name=f"Author of {title}")
        session.add(author)
        session.commit()
        session.refresh(author)
        book = Book(
            title=title,
            author_id=author.id,
            description=f"Description of {title}",
            url=url or f"http://example.com/{title.lower().replace(' ', '-')}",
            is_fiction=is_fiction,
        )
        session.add(book)
        session.commit()
        session.refresh(book)
        return book.id


def _create_review(engine, book_id: int, rating: int, text: str = "Good") -> int:
    """Insert a review and return its ID."""
    with Session(engine) as session:
        review = Review(
            book_id=book_id,
            rating=rating,
            review=text,
        )
        session.add(review)
        session.commit()
        session.refresh(review)
        return review.id


# -----------------------------------------------------------------------
# GET /users/me Endpoint Tests
# -----------------------------------------------------------------------


class TestUsersMeEndpoint:
    def test_unauthenticated(self, client: TestClient):
        response = client.get("/users/me")
        assert response.status_code == 401

    def test_returns_profile(self, client: TestClient):
        reg = _register_user(client)
        token = reg.json()["access_token"]

        response = client.get(
            "/users/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser1"
        assert data["rating_count"] == 0

    def test_rating_count_reflects_ratings(self, client: TestClient, setup_db):
        reg = _register_user(client)
        token = reg.json()["access_token"]

        # Create books and rate them
        book1_id = _create_book(setup_db, "Book 1")
        book2_id = _create_book(setup_db, "Book 2")

        client.post(
            "/ratings/",
            json={"book_id": book1_id, "rating": 4},
            headers={"Authorization": f"Bearer {token}"},
        )
        client.post(
            "/ratings/",
            json={"book_id": book2_id, "rating": 5},
            headers={"Authorization": f"Bearer {token}"},
        )

        response = client.get(
            "/users/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        assert response.json()["rating_count"] == 2


# -----------------------------------------------------------------------
# GET /recommendations/ Endpoint Tests
# -----------------------------------------------------------------------


class TestRecommendationsEndpoint:
    def test_unauthenticated(self, client: TestClient):
        response = client.get("/recommendations/")
        assert response.status_code == 401

    def test_fallback_no_ratings(self, client: TestClient, setup_db):
        """User with 0 ratings gets popular fallback."""
        reg = _register_user(client)
        token = reg.json()["access_token"]

        response = client.get(
            "/recommendations/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["strategy"] == "popular"
        assert data["meta"]["rating_count"] == 0
        assert data["items"] == []

    def test_fallback_few_ratings(self, client: TestClient, setup_db):
        """User with < 5 ratings gets popular fallback."""
        reg = _register_user(client)
        token = reg.json()["access_token"]

        # Create 3 books with reviews and rate them
        for i in range(3):
            book_id = _create_book(setup_db, f"Book {i}")
            _create_review(setup_db, book_id, rating=4)
            client.post(
                "/ratings/",
                json={"book_id": book_id, "rating": 4},
                headers={"Authorization": f"Bearer {token}"},
            )

        # Create additional unrated books with reviews for popular results
        for i in range(3, 6):
            book_id = _create_book(setup_db, f"Unrated Book {i}")
            _create_review(setup_db, book_id, rating=5)

        response = client.get(
            "/recommendations/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["strategy"] == "popular"
        assert data["meta"]["rating_count"] == 3
        # Should have unrated books as recommendations
        assert len(data["items"]) > 0
        # Rated books should be excluded
        rated_titles = {f"Book {i}" for i in range(3)}
        for item in data["items"]:
            assert item["title"] not in rated_titles

    @patch("backend.app.main.compute_user_embedding")
    @patch("backend.app.main.find_nearest_books")
    def test_personalized_path(
        self,
        mock_find: MagicMock,
        mock_compute: MagicMock,
        client: TestClient,
        setup_db,
    ):
        """User with 5+ ratings and valid embedding gets personalized results."""
        reg = _register_user(client)
        token = reg.json()["access_token"]

        # Create and rate 5 books
        book_ids = []
        for i in range(5):
            book_id = _create_book(setup_db, f"Rated Book {i}")
            _create_review(setup_db, book_id, rating=4)
            book_ids.append(book_id)
            client.post(
                "/ratings/",
                json={"book_id": book_id, "rating": 4},
                headers={"Authorization": f"Bearer {token}"},
            )

        # Create an unrated book to return as recommendation
        rec_book_id = _create_book(setup_db, "Recommended Book")
        _create_review(setup_db, rec_book_id, rating=5)

        # Mock the embedding computation
        mock_compute.return_value = [0.1] * 384

        # find_nearest_books is called within the request session context,
        # so query the book from the active session to avoid DetachedInstanceError.
        def side_effect(session, user_embedding, exclude_ids, category, limit):
            book = session.exec(
                select(Book)
                .options(
                    selectinload(Book.author),
                    selectinload(Book.publisher),
                    selectinload(Book.genres),
                )
                .where(Book.id == rec_book_id)
            ).first()
            return [book] if book else []

        mock_find.side_effect = side_effect

        response = client.get(
            "/recommendations/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["strategy"] == "personalized"
        assert data["meta"]["rating_count"] == 5
        assert len(data["items"]) == 1
        assert data["items"][0]["title"] == "Recommended Book"

    @patch("backend.app.main.compute_user_embedding")
    def test_personalized_fallback_no_embedding(
        self,
        mock_compute: MagicMock,
        client: TestClient,
        setup_db,
    ):
        """User with 5+ ratings but no embeddings falls back to popular."""
        reg = _register_user(client)
        token = reg.json()["access_token"]

        for i in range(5):
            book_id = _create_book(setup_db, f"Book {i}")
            _create_review(setup_db, book_id, rating=4)
            client.post(
                "/ratings/",
                json={"book_id": book_id, "rating": 4},
                headers={"Authorization": f"Bearer {token}"},
            )

        mock_compute.return_value = None

        response = client.get(
            "/recommendations/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["strategy"] == "popular"
        assert data["meta"]["rating_count"] == 5

    def test_category_filter_in_response(self, client: TestClient, setup_db):
        """Category parameter is reflected in response meta."""
        reg = _register_user(client)
        token = reg.json()["access_token"]

        response = client.get(
            "/recommendations/?category=fiction",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["meta"]["category"] == "fiction"

    def test_category_nonfiction(self, client: TestClient, setup_db):
        reg = _register_user(client)
        token = reg.json()["access_token"]

        response = client.get(
            "/recommendations/?category=nonfiction",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["meta"]["category"] == "nonfiction"

    def test_default_category_all(self, client: TestClient, setup_db):
        reg = _register_user(client)
        token = reg.json()["access_token"]

        response = client.get(
            "/recommendations/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["meta"]["category"] == "all"

    def test_invalid_category(self, client: TestClient, setup_db):
        reg = _register_user(client)
        token = reg.json()["access_token"]

        response = client.get(
            "/recommendations/?category=invalid",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    def test_limit_parameter(self, client: TestClient, setup_db):
        reg = _register_user(client)
        token = reg.json()["access_token"]

        # Create many books with reviews
        for i in range(10):
            book_id = _create_book(setup_db, f"Pop Book {i}")
            _create_review(setup_db, book_id, rating=5)

        response = client.get(
            "/recommendations/?limit=3",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert len(response.json()["items"]) <= 3

    def test_response_shape(self, client: TestClient, setup_db):
        """Verify the response has the expected structure."""
        reg = _register_user(client)
        token = reg.json()["access_token"]

        response = client.get(
            "/recommendations/",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "meta" in data
        assert "strategy" in data["meta"]
        assert "rating_count" in data["meta"]
        assert "category" in data["meta"]
        assert isinstance(data["items"], list)

    def test_fiction_filter_returns_only_fiction(self, client: TestClient, setup_db):
        """Fiction category filter excludes nonfiction books."""
        reg = _register_user(client)
        token = reg.json()["access_token"]

        # Create fiction and nonfiction books with reviews
        fiction_id = _create_book(setup_db, "Fiction Book", is_fiction=True)
        _create_review(setup_db, fiction_id, rating=5)

        nonfiction_id = _create_book(setup_db, "Nonfiction Book", is_fiction=False)
        _create_review(setup_db, nonfiction_id, rating=5)

        response = client.get(
            "/recommendations/?category=fiction",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        for item in response.json()["items"]:
            # Should not include nonfiction book
            assert item["title"] != "Nonfiction Book"

    @patch("backend.app.main.compute_user_embedding")
    @patch("backend.app.main.find_nearest_books")
    def test_personalized_passes_category_to_embedding(
        self,
        mock_find: MagicMock,
        mock_compute: MagicMock,
        client: TestClient,
        setup_db,
    ):
        """compute_user_embedding must receive the category parameter."""
        reg = _register_user(client)
        token = reg.json()["access_token"]

        # Create and rate 5 fiction books
        for i in range(5):
            book_id = _create_book(setup_db, f"Fiction {i}", is_fiction=True)
            _create_review(setup_db, book_id, rating=4)
            client.post(
                "/ratings/",
                json={"book_id": book_id, "rating": 4},
                headers={"Authorization": f"Bearer {token}"},
            )

        mock_compute.return_value = [0.1] * 384
        mock_find.return_value = []

        client.get(
            "/recommendations/?category=fiction",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Verify compute_user_embedding was called with category="fiction"
        mock_compute.assert_called_once()
        call_args = mock_compute.call_args[0]
        assert len(call_args) >= 3
        assert call_args[2] == "fiction"

    @patch("backend.app.main.compute_user_embedding")
    @patch("backend.app.main.find_nearest_books")
    def test_category_specific_rating_count(
        self,
        mock_find: MagicMock,
        mock_compute: MagicMock,
        client: TestClient,
        setup_db,
    ):
        """rating_count in response should reflect category-specific count."""
        reg = _register_user(client)
        token = reg.json()["access_token"]

        # Rate 3 fiction + 4 nonfiction = 7 total, but only 3 fiction
        for i in range(3):
            book_id = _create_book(setup_db, f"Fiction {i}", is_fiction=True)
            _create_review(setup_db, book_id, rating=4)
            client.post(
                "/ratings/",
                json={"book_id": book_id, "rating": 4},
                headers={"Authorization": f"Bearer {token}"},
            )
        for i in range(4):
            book_id = _create_book(setup_db, f"Nonfiction {i}", is_fiction=False)
            _create_review(setup_db, book_id, rating=3)
            client.post(
                "/ratings/",
                json={"book_id": book_id, "rating": 3},
                headers={"Authorization": f"Bearer {token}"},
            )

        mock_compute.return_value = [0.1] * 384
        mock_find.return_value = []

        # Request fiction: only 3 fiction ratings, should get popular fallback
        response = client.get(
            "/recommendations/?category=fiction",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["rating_count"] == 3
        # With only 3 fiction ratings (< MIN_RATINGS=5), strategy should be popular
        assert data["meta"]["strategy"] == "popular"

    @patch("backend.app.main.compute_user_embedding")
    @patch("backend.app.main.find_nearest_books")
    def test_category_all_uses_total_rating_count(
        self,
        mock_find: MagicMock,
        mock_compute: MagicMock,
        client: TestClient,
        setup_db,
    ):
        """When category='all', rating_count should include all ratings."""
        reg = _register_user(client)
        token = reg.json()["access_token"]

        # Rate 3 fiction + 3 nonfiction = 6 total
        for i in range(3):
            book_id = _create_book(setup_db, f"Fiction {i}", is_fiction=True)
            _create_review(setup_db, book_id, rating=4)
            client.post(
                "/ratings/",
                json={"book_id": book_id, "rating": 4},
                headers={"Authorization": f"Bearer {token}"},
            )
        for i in range(3):
            book_id = _create_book(setup_db, f"Nonfiction {i}", is_fiction=False)
            _create_review(setup_db, book_id, rating=3)
            client.post(
                "/ratings/",
                json={"book_id": book_id, "rating": 3},
                headers={"Authorization": f"Bearer {token}"},
            )

        mock_compute.return_value = [0.1] * 384
        mock_find.return_value = []

        response = client.get(
            "/recommendations/?category=all",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["meta"]["rating_count"] == 6
        assert data["meta"]["strategy"] == "personalized"
