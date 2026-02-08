import os
os.environ.setdefault("DATABASE_URL", "sqlite:///")
os.environ.setdefault("SECRET_KEY", "test-secret")

import pytest
from pydantic import ValidationError

from backend.db.models import (
    RefreshToken,
    UserCreate,
    RatingCreate,
    AuthResponse,
    UserPublic,
)


class TestRefreshTokenModel:
    """Tests for the RefreshToken SQLModel table."""

    def test_refresh_token_has_required_fields(self):
        token = RefreshToken(
            user_id=1,
            token_hash="abc123hash",
            expires_at="2025-01-01T00:00:00",
        )
        assert token.user_id == 1
        assert token.token_hash == "abc123hash"
        assert token.id is None  # auto-generated

    def test_refresh_token_has_created_at_default(self):
        token = RefreshToken(
            user_id=1,
            token_hash="abc123hash",
            expires_at="2025-01-01T00:00:00",
        )
        assert token.created_at is not None


class TestUserCreateValidation:
    """Tests for UserCreate input validation."""

    def test_valid_username_and_password(self):
        user = UserCreate(username="valid_user1", password="Secret123")
        assert user.username == "valid_user1"

    def test_username_too_short(self):
        with pytest.raises(ValidationError):
            UserCreate(username="ab", password="Secret123")

    def test_username_too_long(self):
        with pytest.raises(ValidationError):
            UserCreate(username="a" * 31, password="Secret123")

    def test_username_invalid_characters(self):
        with pytest.raises(ValidationError):
            UserCreate(username="bad user!", password="Secret123")

    def test_username_with_special_chars_rejected(self):
        with pytest.raises(ValidationError):
            UserCreate(username="user@name", password="Secret123")

    def test_password_too_short(self):
        with pytest.raises(ValidationError):
            UserCreate(username="valid_user", password="Abc1")

    def test_password_no_digit(self):
        with pytest.raises(ValidationError):
            UserCreate(username="valid_user", password="NoDigitsHere")

    def test_password_no_letter(self):
        with pytest.raises(ValidationError):
            UserCreate(username="valid_user", password="12345678")

    def test_password_minimum_valid(self):
        user = UserCreate(username="abc", password="Abcdefg1")
        assert user.password == "Abcdefg1"

    def test_password_too_long(self):
        # 73 characters (exceeds bcrypt's 72-byte limit)
        long_password = "A1" + "x" * 71
        with pytest.raises(ValidationError) as exc_info:
            UserCreate(username="valid_user", password=long_password)
        assert "must not exceed 72 characters" in str(exc_info.value)

    def test_password_maximum_valid(self):
        # Exactly 72 characters (bcrypt's limit)
        max_password = "A1" + "x" * 70
        user = UserCreate(username="valid_user", password=max_password)
        assert user.password == max_password

    def test_username_underscores_allowed(self):
        user = UserCreate(username="user_name_123", password="Secret123")
        assert user.username == "user_name_123"


class TestRatingCreate:
    """Tests for the RatingCreate schema."""

    def test_valid_rating(self):
        rating = RatingCreate(book_id=1, rating=5)
        assert rating.book_id == 1
        assert rating.rating == 5

    def test_rating_below_minimum(self):
        with pytest.raises(ValidationError):
            RatingCreate(book_id=1, rating=0)

    def test_rating_above_maximum(self):
        with pytest.raises(ValidationError):
            RatingCreate(book_id=1, rating=6)

    def test_rating_boundary_low(self):
        rating = RatingCreate(book_id=1, rating=1)
        assert rating.rating == 1

    def test_rating_boundary_high(self):
        rating = RatingCreate(book_id=1, rating=5)
        assert rating.rating == 5


class TestAuthResponse:
    """Tests for the AuthResponse schema."""

    def test_auth_response_fields(self):
        user = UserPublic(id=1, username="testuser")
        response = AuthResponse(
            access_token="jwt.token.here",
            token_type="bearer",
            user=user,
        )
        assert response.access_token == "jwt.token.here"
        assert response.token_type == "bearer"
        assert response.user.username == "testuser"
