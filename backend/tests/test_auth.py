import os
os.environ.setdefault("DATABASE_URL", "sqlite:///")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-jwt")

from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt
from sqlmodel import Session, SQLModel, create_engine

from backend.app.auth import (
    create_access_token,
    create_refresh_token,
    hash_token,
    decode_access_token,
    store_refresh_token,
    validate_refresh_token,
    revoke_refresh_token,
)
from backend.app.config import SECRET_KEY, ALGORITHM
from backend.db.models import RefreshToken, User


@pytest.fixture
def db_session():
    """Create an in-memory SQLite session for testing."""
    engine = create_engine("sqlite://", echo=False)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Create and return a test user."""
    user = User(id=1, username="testuser", password_hash="fakehash")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestCreateAccessToken:
    def test_returns_string(self):
        token = create_access_token(user_id=1, username="testuser")
        assert isinstance(token, str)

    def test_contains_correct_claims(self):
        token = create_access_token(user_id=42, username="alice")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "42"
        assert payload["username"] == "alice"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_token_not_expired_immediately(self):
        token = create_access_token(user_id=1, username="testuser")
        # Should not raise
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload is not None


class TestCreateRefreshToken:
    def test_returns_string(self):
        token = create_refresh_token()
        assert isinstance(token, str)

    def test_tokens_are_unique(self):
        t1 = create_refresh_token()
        t2 = create_refresh_token()
        assert t1 != t2

    def test_sufficient_length(self):
        token = create_refresh_token()
        assert len(token) >= 64


class TestHashToken:
    def test_returns_hex_string(self):
        result = hash_token("some-token")
        assert isinstance(result, str)
        # SHA-256 hex digest is 64 chars
        assert len(result) == 64

    def test_same_input_same_hash(self):
        assert hash_token("token-a") == hash_token("token-a")

    def test_different_input_different_hash(self):
        assert hash_token("token-a") != hash_token("token-b")


class TestDecodeAccessToken:
    def test_valid_token_returns_payload(self):
        token = create_access_token(user_id=1, username="testuser")
        payload = decode_access_token(token)
        assert payload["sub"] == "1"
        assert payload["username"] == "testuser"

    def test_invalid_token_raises(self):
        with pytest.raises(Exception):
            decode_access_token("invalid.token.here")

    def test_expired_token_raises(self):
        from jose import jwt as jose_jwt
        expired_payload = {
            "sub": "1",
            "username": "testuser",
            "type": "access",
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        }
        token = jose_jwt.encode(expired_payload, SECRET_KEY, algorithm=ALGORITHM)
        with pytest.raises(Exception):
            decode_access_token(token)


class TestRefreshTokenCRUD:
    def test_store_refresh_token(self, db_session: Session, test_user: User):
        raw_token = "raw-refresh-token-value"
        store_refresh_token(db_session, test_user.id, raw_token)

        from sqlmodel import select as sel
        stored = db_session.exec(sel(RefreshToken)).first()
        assert stored is not None
        assert stored.user_id == test_user.id
        assert stored.token_hash == hash_token(raw_token)

    def test_validate_refresh_token_valid(self, db_session: Session, test_user: User):
        raw_token = "valid-refresh-token"
        store_refresh_token(db_session, test_user.id, raw_token)

        result = validate_refresh_token(db_session, raw_token)
        assert result is not None
        assert result.user_id == test_user.id

    def test_validate_refresh_token_expired(self, db_session: Session, test_user: User):
        raw_token = "expired-refresh-token"
        token_hash = hash_token(raw_token)
        expired_token = RefreshToken(
            user_id=test_user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        )
        db_session.add(expired_token)
        db_session.commit()

        result = validate_refresh_token(db_session, raw_token)
        assert result is None

    def test_validate_refresh_token_nonexistent(self, db_session: Session):
        result = validate_refresh_token(db_session, "nonexistent-token")
        assert result is None

    def test_revoke_refresh_token(self, db_session: Session, test_user: User):
        raw_token = "token-to-revoke"
        store_refresh_token(db_session, test_user.id, raw_token)

        revoke_refresh_token(db_session, raw_token)

        result = validate_refresh_token(db_session, raw_token)
        assert result is None
