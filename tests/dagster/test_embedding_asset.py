"""Unit tests for the review_embeddings Dagster asset.

Tests the asset that generates embeddings for review texts using
sentence-transformers. Uses in-memory SQLite for database tests and
a patched SentenceTransformer model.

Note: SQLite does not support pgvector's Vector type natively. The
Vector column is created by SQLModel as a generic column in SQLite.
The asset's WHERE embedding IS NULL query works because SQLite treats
the column as a standard nullable column.
"""
import tempfile
from datetime import date, datetime
from unittest.mock import MagicMock, call, patch

import pytest

import dagster as dg
import numpy as np
from sqlalchemy import create_engine, text as sa_text
from sqlmodel import Session, SQLModel, select


def _make_test_db() -> tuple[str, str]:
    """Create a temporary SQLite database with the schema.

    Returns a (connection_string, db_path) tuple. Uses a file-based
    SQLite DB so multiple connections can share data.
    """
    import backend.db.models  # noqa: F401 -- registers models

    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db_file.name
    db_file.close()
    conn_str = f"sqlite:///{db_path}"

    engine = create_engine(conn_str)
    SQLModel.metadata.create_all(engine)
    engine.dispose()

    return conn_str, db_path


def _seed_reviews(conn_str: str, count: int = 3) -> list[int]:
    """Insert test book and reviews into the database.

    Returns the list of review IDs that were created.
    """
    from backend.db.models import Author, Book, Critic, Publication, Publisher, Review

    engine = create_engine(conn_str)
    review_ids = []

    with Session(engine) as session:
        author = Author(name="Test Author")
        publisher = Publisher(name="Test Publisher")
        session.add(author)
        session.add(publisher)
        session.flush()

        book = Book(
            title="Test Book",
            author=author,
            publisher=publisher,
            publish_date=date(2025, 1, 1),
            description="A test book.",
            url="https://bookmarks.reviews/reviews/test/",
            cover=None,
            is_fiction=True,
            last_scraped=datetime(2025, 10, 13, 11, 0, 0),
        )
        session.add(book)
        session.flush()

        critic = Critic(name="Test Critic")
        publication = Publication(name="Test Publication")
        session.add(critic)
        session.add(publication)
        session.flush()

        for i in range(count):
            review = Review(
                book_id=book.id,
                critic=critic,
                publication=publication,
                rating=4,
                review=f"This is review number {i + 1} with enough text for embedding.",
                url=f"https://example.com/review-{i + 1}",
            )
            session.add(review)
            session.flush()
            review_ids.append(review.id)

        session.commit()

    engine.dispose()
    return review_ids


def _make_fake_st(num_texts: int, dims: int = 384) -> MagicMock:
    """Create a fake SentenceTransformer that returns deterministic embeddings."""
    fake_embeddings = np.random.RandomState(42).rand(num_texts, dims).astype(np.float32)
    mock_model = MagicMock()
    mock_model.encode.return_value = fake_embeddings
    return mock_model


class TestReviewEmbeddingsAssetDefinition:
    """Tests that the review_embeddings asset is properly defined."""

    def test_asset_exists(self) -> None:
        """The review_embeddings asset should be importable."""
        from litmatch.defs.assets.embedding import review_embeddings

        assert review_embeddings is not None

    def test_asset_is_dagster_asset(self) -> None:
        """review_embeddings should be a Dagster asset."""
        from litmatch.defs.assets.embedding import review_embeddings

        assert hasattr(review_embeddings, "op")

    def test_asset_depends_on_load_books(self) -> None:
        """review_embeddings should declare load_books as a dependency."""
        from litmatch.defs.assets.embedding import review_embeddings

        dep_keys = review_embeddings.asset_deps[review_embeddings.key]
        assert dg.AssetKey("load_books") in dep_keys


class TestReviewEmbeddingsAssetLogic:
    """Tests for the review_embeddings asset logic.

    Uses real DatabaseResource and EmbeddingModelResource instances
    with the SentenceTransformer patched to avoid loading the actual
    ML model (~80 MB).
    """

    def test_encodes_reviews_without_embeddings(self) -> None:
        """The asset should encode all reviews that have no embedding yet."""
        from litmatch.defs.assets.embedding import review_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_reviews(conn_str, count=3)

        mock_st = _make_fake_st(3)
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_st,
        ):
            result = review_embeddings(context)

        # Verify the model was called with the review texts
        mock_st.encode.assert_called_once()
        call_args = mock_st.encode.call_args[0][0]
        assert len(call_args) == 3
        assert all("review number" in t for t in call_args)

        # Verify result is a MaterializeResult with metadata
        assert isinstance(result, dg.MaterializeResult)
        assert result.metadata["reviews_encoded"] == 3

    def test_skips_reviews_with_existing_embeddings(self) -> None:
        """The asset should skip reviews that already have embeddings."""
        from litmatch.defs.assets.embedding import review_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        review_ids = _seed_reviews(conn_str, count=3)

        # Manually set embedding on the first review
        engine = create_engine(conn_str)
        with Session(engine) as session:
            session.execute(
                sa_text("UPDATE review SET embedding = :emb WHERE id = :id"),
                {"emb": str([0.1] * 384), "id": review_ids[0]},
            )
            session.commit()
        engine.dispose()

        mock_st = _make_fake_st(2)
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_st,
        ):
            result = review_embeddings(context)

        # Only 2 reviews should be encoded (the one with embedding is skipped)
        call_args = mock_st.encode.call_args[0][0]
        assert len(call_args) == 2
        assert isinstance(result, dg.MaterializeResult)
        assert result.metadata["reviews_encoded"] == 2

    def test_no_reviews_to_encode_returns_early(self) -> None:
        """When all reviews have embeddings, the asset returns zero encoded."""
        from litmatch.defs.assets.embedding import review_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        review_ids = _seed_reviews(conn_str, count=2)

        # Set all reviews as having embeddings
        engine = create_engine(conn_str)
        with Session(engine) as session:
            for rid in review_ids:
                session.execute(
                    sa_text("UPDATE review SET embedding = :emb WHERE id = :id"),
                    {"emb": str([0.1] * 384), "id": rid},
                )
            session.commit()
        engine.dispose()

        mock_st = MagicMock()
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_st,
        ):
            result = review_embeddings(context)

        # encode() should not have been called on the model
        mock_st.encode.assert_not_called()
        assert isinstance(result, dg.MaterializeResult)
        assert result.metadata["reviews_encoded"] == 0

    def test_empty_database_returns_zero(self) -> None:
        """When there are no reviews at all, asset returns zero encoded."""
        from litmatch.defs.assets.embedding import review_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()

        mock_st = MagicMock()
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_st,
        ):
            result = review_embeddings(context)

        mock_st.encode.assert_not_called()
        assert isinstance(result, dg.MaterializeResult)
        assert result.metadata["reviews_encoded"] == 0

    def test_batch_processing_multiple_reviews(self) -> None:
        """Reviews should be processed and all results reported in metadata."""
        from litmatch.defs.assets.embedding import review_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_reviews(conn_str, count=5)

        mock_st = _make_fake_st(5)
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_st,
        ):
            result = review_embeddings(context)

        assert isinstance(result, dg.MaterializeResult)
        assert result.metadata["reviews_encoded"] == 5
        assert result.metadata["model_name"] == "all-MiniLM-L6-v2"
        assert result.metadata["dimensions"] == 384

    def test_metadata_includes_model_info(self) -> None:
        """MaterializeResult metadata should include model name and dimensions."""
        from litmatch.defs.assets.embedding import review_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_reviews(conn_str, count=1)

        mock_st = _make_fake_st(1)
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_st,
        ):
            result = review_embeddings(context)

        assert "reviews_encoded" in result.metadata
        assert "model_name" in result.metadata
        assert "dimensions" in result.metadata
        assert result.metadata["model_name"] == "all-MiniLM-L6-v2"
        assert result.metadata["dimensions"] == 384

    def test_writes_embeddings_to_database(self) -> None:
        """The asset should write embeddings back to review rows."""
        from litmatch.defs.assets.embedding import review_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource
        from backend.db.models import Review

        conn_str, _ = _make_test_db()
        _seed_reviews(conn_str, count=2)

        mock_st = _make_fake_st(2)
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_st,
        ):
            review_embeddings(context)

        # Verify embeddings were stored
        engine = create_engine(conn_str)
        with Session(engine) as session:
            reviews = session.exec(select(Review)).all()
            for review in reviews:
                assert review.embedding is not None
        engine.dispose()

    def test_idempotent_second_run_encodes_nothing(self) -> None:
        """Running the asset twice should encode reviews only on first run."""
        from litmatch.defs.assets.embedding import review_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_reviews(conn_str, count=2)

        mock_st = _make_fake_st(2)
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        # First run: encodes all reviews
        context1 = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_st,
        ):
            result1 = review_embeddings(context1)
        assert result1.metadata["reviews_encoded"] == 2

        # Reset the mock
        mock_st.encode.reset_mock()

        # Second run: should encode nothing
        context2 = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_st,
        ):
            result2 = review_embeddings(context2)
        assert result2.metadata["reviews_encoded"] == 0
        mock_st.encode.assert_not_called()


class TestEngineDisposal:
    """[H-2] Tests that the database engine is properly disposed after use.

    SQLAlchemy engines hold connection pools. If not disposed, connections
    accumulate and exhaust the database connection limit.

    Tests use a mock engine returned by a mock DatabaseResource to verify
    that engine.dispose() is called in all code paths.
    """

    def test_engine_disposed_on_success(self) -> None:
        """Engine should be disposed after successful embedding generation."""
        from litmatch.defs.assets.embedding import review_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_reviews(conn_str, count=2)

        mock_st = _make_fake_st(2)
        real_engine = create_engine(conn_str)
        mock_dispose = MagicMock(wraps=real_engine.dispose)
        real_engine.dispose = mock_dispose

        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_st,
        ), patch(
            "litmatch.defs.assets.embedding.DatabaseResource.get_engine",
            return_value=real_engine,
        ):
            result = review_embeddings(context)

        mock_dispose.assert_called_once()
        assert isinstance(result, dg.MaterializeResult)
        assert result.metadata["reviews_encoded"] == 2

    def test_engine_disposed_on_no_reviews(self) -> None:
        """Engine should be disposed even when no reviews need encoding."""
        from litmatch.defs.assets.embedding import review_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()

        mock_st = MagicMock()
        real_engine = create_engine(conn_str)
        mock_dispose = MagicMock(wraps=real_engine.dispose)
        real_engine.dispose = mock_dispose

        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_st,
        ), patch(
            "litmatch.defs.assets.embedding.DatabaseResource.get_engine",
            return_value=real_engine,
        ):
            review_embeddings(context)

        mock_dispose.assert_called_once()

    def test_engine_disposed_on_encode_error(self) -> None:
        """Engine should be disposed even if encode() raises an error."""
        from litmatch.defs.assets.embedding import review_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_reviews(conn_str, count=1)

        mock_st = MagicMock()
        mock_st.encode.side_effect = RuntimeError("CUDA out of memory")
        real_engine = create_engine(conn_str)
        mock_dispose = MagicMock(wraps=real_engine.dispose)
        real_engine.dispose = mock_dispose

        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_st,
        ), patch(
            "litmatch.defs.assets.embedding.DatabaseResource.get_engine",
            return_value=real_engine,
        ):
            with pytest.raises(dg.Failure):
                review_embeddings(context)

        mock_dispose.assert_called_once()


class TestNullEmptyTextGuards:
    """[HIGH-4] Tests that NULL and empty review texts are filtered.

    Reviews with NULL, empty string, or whitespace-only text must be
    skipped rather than sent to the model, which would produce garbage
    embeddings or errors.
    """

    def _seed_reviews_with_text(
        self, conn_str: str, texts: list[str]
    ) -> list[int]:
        """Insert reviews with specific text values (including empty strings).

        The Review model requires review: str (NOT NULL), so NULL values
        are not possible via normal ORM operations. This helper tests
        realistic edge cases: empty strings and whitespace-only text.
        """
        from backend.db.models import (
            Author, Book, Critic, Publication, Publisher, Review,
        )

        engine = create_engine(conn_str)
        review_ids = []

        with Session(engine) as session:
            author = Author(name="Test Author")
            publisher = Publisher(name="Test Publisher")
            session.add(author)
            session.add(publisher)
            session.flush()

            book = Book(
                title="Test Book",
                author=author,
                publisher=publisher,
                publish_date=date(2025, 1, 1),
                description="A test book.",
                url="https://bookmarks.reviews/reviews/test/",
                cover=None,
                is_fiction=True,
                last_scraped=datetime(2025, 10, 13, 11, 0, 0),
            )
            session.add(book)
            session.flush()

            critic = Critic(name="Test Critic")
            publication = Publication(name="Test Publication")
            session.add(critic)
            session.add(publication)
            session.flush()

            for i, text in enumerate(texts):
                review = Review(
                    book_id=book.id,
                    critic=critic,
                    publication=publication,
                    rating=4,
                    review=text,
                    url=f"https://example.com/review-{i + 1}",
                )
                session.add(review)
                session.flush()
                review_ids.append(review.id)

            session.commit()

        engine.dispose()
        return review_ids

    def test_filters_none_text_from_query_results(self) -> None:
        """NULL text from SQL results should be filtered before encoding.

        The Review model defines review as NOT NULL, but defensive code
        should still handle None from raw SQL results. This test mocks
        the database query to return a None text row.
        """
        from litmatch.defs.assets.embedding import review_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()

        # Mock the session query to return rows with None text
        mock_rows = [(1, None), (2, "Valid review text.")]
        mock_st = _make_fake_st(1)
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_st,
        ), patch(
            "litmatch.defs.assets.embedding.Session"
        ) as MockSession:
            mock_session_instance = MagicMock()
            mock_session_instance.__enter__ = MagicMock(
                return_value=mock_session_instance
            )
            mock_session_instance.__exit__ = MagicMock(return_value=False)
            mock_session_instance.exec.return_value.all.return_value = mock_rows
            MockSession.return_value = mock_session_instance

            result = review_embeddings(context)

        # Only the valid text should be encoded (None filtered out)
        call_args = mock_st.encode.call_args[0][0]
        assert len(call_args) == 1
        assert "Valid review" in call_args[0]
        assert result.metadata["reviews_encoded"] == 1
        assert result.metadata["reviews_skipped"] == 1

    def test_skips_empty_review_text(self) -> None:
        """Reviews with empty string text should be skipped."""
        from litmatch.defs.assets.embedding import review_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        self._seed_reviews_with_text(conn_str, [
            "",
            "Good review with substance.",
        ])

        mock_st = _make_fake_st(1)
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_st,
        ):
            result = review_embeddings(context)

        call_args = mock_st.encode.call_args[0][0]
        assert len(call_args) == 1
        assert "Good review" in call_args[0]
        assert result.metadata["reviews_encoded"] == 1

    def test_skips_whitespace_only_review_text(self) -> None:
        """Reviews with whitespace-only text should be skipped."""
        from litmatch.defs.assets.embedding import review_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        self._seed_reviews_with_text(conn_str, [
            "   \t\n  ",
            "Substantial review content here.",
        ])

        mock_st = _make_fake_st(1)
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_st,
        ):
            result = review_embeddings(context)

        call_args = mock_st.encode.call_args[0][0]
        assert len(call_args) == 1
        assert "Substantial" in call_args[0]
        assert result.metadata["reviews_encoded"] == 1

    def test_all_texts_empty_skips_encoding(self) -> None:
        """When all review texts are empty or whitespace, encode is not called."""
        from litmatch.defs.assets.embedding import review_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        self._seed_reviews_with_text(conn_str, ["", "   ", "\t\n"])

        mock_st = MagicMock()
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_st,
        ):
            result = review_embeddings(context)

        mock_st.encode.assert_not_called()
        assert result.metadata["reviews_encoded"] == 0
        assert result.metadata["reviews_skipped"] == 3

    def test_metadata_reports_skipped_count(self) -> None:
        """MaterializeResult should include count of skipped reviews."""
        from litmatch.defs.assets.embedding import review_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        self._seed_reviews_with_text(conn_str, [
            "",
            "   ",
            "Valid review text.",
        ])

        mock_st = _make_fake_st(1)
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_st,
        ):
            result = review_embeddings(context)

        assert result.metadata["reviews_skipped"] == 2
        assert result.metadata["reviews_encoded"] == 1


class TestEncodeErrorHandling:
    """[HIGH-1] Tests that model encode() errors are caught and re-raised.

    Unhandled model errors produce cryptic stack traces. Wrapping encode()
    in try-except with detailed context enables better debugging.
    """

    def test_encode_runtime_error_raises_dagster_failure(self) -> None:
        """A RuntimeError from encode() should be wrapped in dg.Failure."""
        from litmatch.defs.assets.embedding import review_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_reviews(conn_str, count=2)

        mock_st = MagicMock()
        mock_st.encode.side_effect = RuntimeError("CUDA out of memory")
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_st,
        ):
            with pytest.raises(dg.Failure, match="Embedding encode failed"):
                review_embeddings(context)

    def test_encode_generic_exception_raises_dagster_failure(self) -> None:
        """Any Exception from encode() should be wrapped in dg.Failure."""
        from litmatch.defs.assets.embedding import review_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_reviews(conn_str, count=1)

        mock_st = MagicMock()
        mock_st.encode.side_effect = ValueError("Invalid input dimension")
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_st,
        ):
            with pytest.raises(dg.Failure, match="Embedding encode failed"):
                review_embeddings(context)

    def test_encode_error_includes_batch_context(self) -> None:
        """The Failure message should include batch offset for debugging."""
        from litmatch.defs.assets.embedding import review_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_reviews(conn_str, count=3)

        mock_st = MagicMock()
        mock_st.encode.side_effect = RuntimeError("Model crashed")
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_st,
        ):
            with pytest.raises(dg.Failure, match="batch"):
                review_embeddings(context)


class TestDimensionAgnosticDocumentation:
    """[HIGH-2] Tests that asset docs do not hardcode specific dimensions.

    The model dimensions are configurable and depend on the selected model.
    Asset descriptions and docstrings should not promise a specific value
    like '384-dim'.
    """

    def test_asset_description_is_dimension_agnostic(self) -> None:
        """The asset description should not hardcode a specific dimension."""
        from litmatch.defs.assets.embedding import review_embeddings

        specs = list(review_embeddings.specs)
        description = specs[0].description
        assert "384" not in description, (
            "Asset description should not hardcode 384 dimensions; "
            "use dimension-agnostic language instead."
        )

    def test_metadata_reflects_actual_model_dimensions(self) -> None:
        """Metadata 'dimensions' should reflect the configured model, not a constant.

        Uses the no-reviews early-return path to avoid writing 768-dim
        embeddings to a Vector(384) column in the test DB.
        """
        from litmatch.defs.assets.embedding import review_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        # No reviews seeded -- triggers early return with metadata

        mock_st = MagicMock()
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource(model_name="all-mpnet-base-v2")

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch(
            "sentence_transformers.SentenceTransformer",
            return_value=mock_st,
        ):
            result = review_embeddings(context)

        # Dimensions in metadata should match the model's actual dimensions
        assert result.metadata["dimensions"] == 768
        assert result.metadata["model_name"] == "all-mpnet-base-v2"


class TestReviewEmbeddingsDimensionValidation:
    """Tests that review_embeddings raises dg.Failure for wrong-dim embeddings."""

    def test_wrong_dim_raises_dagster_failure(self) -> None:
        """review_embeddings should raise dg.Failure when encode returns wrong dims."""
        from litmatch.defs.assets.embedding import review_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_reviews(conn_str, count=2)

        # Return 128-dim embeddings instead of expected 384-dim
        mock_st = _make_fake_st(2, dims=128)
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch("sentence_transformers.SentenceTransformer", return_value=mock_st):
            with pytest.raises(dg.Failure, match="Embedding dimension mismatch"):
                review_embeddings(context)

    def test_correct_dim_does_not_raise(self) -> None:
        """review_embeddings should NOT raise for correct 384-dim embeddings."""
        from litmatch.defs.assets.embedding import review_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_reviews(conn_str, count=2)

        mock_st = _make_fake_st(2, dims=384)
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch("sentence_transformers.SentenceTransformer", return_value=mock_st):
            result = review_embeddings(context)

        assert result.metadata["reviews_encoded"] == 2


class TestGenreEmbeddingsDimensionValidation:
    """Tests that genre_embeddings raises dg.Failure for wrong-dim embeddings."""

    def test_wrong_dim_raises_dagster_failure(self) -> None:
        """genre_embeddings should raise dg.Failure when encode returns wrong dims."""
        from litmatch.defs.assets.embedding import genre_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource
        from backend.db.models import Genre

        conn_str, _ = _make_test_db()

        # Seed a genre with no embedding
        engine = create_engine(conn_str)
        with Session(engine) as session:
            genre = Genre(name="Test Genre")
            session.add(genre)
            session.commit()
        engine.dispose()

        # Return 512-dim embeddings instead of expected 384-dim
        mock_st = MagicMock()
        wrong_dim_emb = np.random.RandomState(42).rand(1, 512).astype(np.float32)
        mock_st.encode.return_value = wrong_dim_emb

        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch("sentence_transformers.SentenceTransformer", return_value=mock_st):
            with pytest.raises(dg.Failure, match="Embedding dimension mismatch"):
                genre_embeddings(context)
