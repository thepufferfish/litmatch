"""Unit tests for the book_description_embeddings Dagster asset.

Tests the asset that generates embeddings for book description texts using
sentence-transformers. Uses in-memory SQLite for database tests and
a patched SentenceTransformer model.

Note: SQLite does not support pgvector's Vector type natively. The
Vector column is created by SQLModel as a generic column in SQLite.
"""
import json
import tempfile
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import dagster as dg
import numpy as np
import pytest
from sqlalchemy import create_engine, text as sa_text
from sqlmodel import Session, SQLModel, select


def _make_test_db() -> tuple[str, str]:
    """Create a temporary SQLite database with the schema."""
    import backend.db.models  # noqa: F401 -- registers models

    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    db_path = db_file.name
    db_file.close()
    conn_str = f"sqlite:///{db_path}"

    engine = create_engine(conn_str)
    SQLModel.metadata.create_all(engine)
    engine.dispose()

    return conn_str, db_path


def _seed_book(
    conn_str: str,
    title: str,
    description: str | None = "A test book description.",
) -> int:
    """Insert a book with the given description. Returns book_id."""
    from backend.db.models import Author, Book, Publisher

    engine = create_engine(conn_str)

    with Session(engine) as session:
        author = Author(name=f"Author for {title}")
        publisher = Publisher(name=f"Publisher for {title}")
        session.add(author)
        session.add(publisher)
        session.flush()

        book = Book(
            title=title,
            author=author,
            publisher=publisher,
            publish_date=date(2025, 1, 1),
            description=description or "",
            url=f"https://bookmarks.reviews/reviews/{title.lower().replace(' ', '-')}/",
            cover=None,
            is_fiction=True,
            last_scraped=datetime(2025, 10, 13, 11, 0, 0),
        )
        session.add(book)
        session.flush()
        book_id = book.id
        session.commit()

    engine.dispose()
    return book_id


def _seed_book_embedding(conn_str: str, book_id: int) -> None:
    """Insert a BookEmbedding row (with NULL embeddings) for the given book."""
    from backend.db.models import BookEmbedding

    engine = create_engine(conn_str)
    with Session(engine) as session:
        be = BookEmbedding(
            book_id=book_id,
            updated_at=datetime.now(timezone.utc),
        )
        session.add(be)
        session.commit()
    engine.dispose()


def _set_description_embedding(
    conn_str: str, book_id: int, emb: list[float]
) -> None:
    """Set description_embedding for a book_embeddings row via raw SQL."""
    engine = create_engine(conn_str)
    with Session(engine) as session:
        session.execute(
            sa_text(
                "UPDATE book_embeddings SET description_embedding = :emb WHERE book_id = :id"
            ),
            {"emb": json.dumps(emb), "id": book_id},
        )
        session.commit()
    engine.dispose()


def _get_description_embedding(conn_str: str, book_id: int) -> str | None:
    """Read the raw description_embedding from the book_embeddings table."""
    engine = create_engine(conn_str)
    with Session(engine) as session:
        result = session.execute(
            sa_text(
                "SELECT description_embedding FROM book_embeddings WHERE book_id = :id"
            ),
            {"id": book_id},
        ).one_or_none()
    engine.dispose()
    return result[0] if result else None


def _make_fake_st(num_texts: int, dims: int = 384) -> MagicMock:
    """Create a fake SentenceTransformer that returns deterministic embeddings."""
    fake_embeddings = np.random.RandomState(42).rand(num_texts, dims).astype(np.float32)
    mock_model = MagicMock()
    mock_model.encode.return_value = fake_embeddings
    return mock_model


class TestBookDescriptionEmbeddingsAssetDefinition:
    """Tests that the book_description_embeddings asset is properly defined."""

    def test_asset_exists(self) -> None:
        from litmatch.defs.assets.embedding import book_description_embeddings

        assert book_description_embeddings is not None

    def test_asset_is_dagster_asset(self) -> None:
        from litmatch.defs.assets.embedding import book_description_embeddings

        assert hasattr(book_description_embeddings, "op")

    def test_asset_depends_on_load_books(self) -> None:
        """book_description_embeddings should declare load_books as a dependency."""
        from litmatch.defs.assets.embedding import book_description_embeddings

        dep_keys = book_description_embeddings.asset_deps[book_description_embeddings.key]
        assert dg.AssetKey("load_books") in dep_keys


class TestBookDescriptionEmbeddingsAssetLogic:
    """Tests for the book_description_embeddings asset logic."""

    def test_embeds_books_with_valid_descriptions(self) -> None:
        """The asset should encode all books with valid descriptions."""
        from litmatch.defs.assets.embedding import book_description_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_book(conn_str, "Book One", "An engaging story about adventure.")
        _seed_book(conn_str, "Book Two", "A compelling drama set in Victorian times.")

        mock_st = _make_fake_st(2)
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch("sentence_transformers.SentenceTransformer", return_value=mock_st):
            result = book_description_embeddings(context)

        assert isinstance(result, dg.MaterializeResult)
        assert result.metadata["books_embedded"] == 2
        assert result.metadata["books_skipped"] == 0

    def test_skips_books_with_empty_descriptions(self) -> None:
        """The asset should skip books with empty string descriptions."""
        from litmatch.defs.assets.embedding import book_description_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_book(conn_str, "Empty Desc Book", "")
        _seed_book(conn_str, "Valid Desc Book", "A real description.")

        mock_st = _make_fake_st(1)
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch("sentence_transformers.SentenceTransformer", return_value=mock_st):
            result = book_description_embeddings(context)

        assert result.metadata["books_embedded"] == 1
        assert result.metadata["books_skipped"] == 1

    def test_skips_books_with_whitespace_only_descriptions(self) -> None:
        """The asset should skip books with whitespace-only descriptions."""
        from litmatch.defs.assets.embedding import book_description_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_book(conn_str, "Whitespace Desc Book", "   \t\n  ")
        _seed_book(conn_str, "Valid Desc Book 2", "Substantive description here.")

        mock_st = _make_fake_st(1)
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch("sentence_transformers.SentenceTransformer", return_value=mock_st):
            result = book_description_embeddings(context)

        assert result.metadata["books_embedded"] == 1
        assert result.metadata["books_skipped"] == 1

    def test_creates_book_embedding_row_when_none_exists(self) -> None:
        """The asset should INSERT a new BookEmbedding row when none exists."""
        from litmatch.defs.assets.embedding import book_description_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        book_id = _seed_book(conn_str, "New Embedding Book", "Great description.")

        mock_st = _make_fake_st(1)
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch("sentence_transformers.SentenceTransformer", return_value=mock_st):
            book_description_embeddings(context)

        # Verify BookEmbedding row was created
        stored = _get_description_embedding(conn_str, book_id)
        assert stored is not None

    def test_updates_existing_book_embedding_row(self) -> None:
        """The asset should UPDATE the description_embedding on an existing BookEmbedding."""
        from litmatch.defs.assets.embedding import book_description_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        book_id = _seed_book(conn_str, "Existing Row Book", "Has good description.")
        _seed_book_embedding(conn_str, book_id)  # Create BookEmbedding row with NULL embeddings

        # Confirm description_embedding is NULL before asset runs
        assert _get_description_embedding(conn_str, book_id) is None

        mock_st = _make_fake_st(1)
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch("sentence_transformers.SentenceTransformer", return_value=mock_st):
            result = book_description_embeddings(context)

        assert result.metadata["books_embedded"] == 1
        stored = _get_description_embedding(conn_str, book_id)
        assert stored is not None

    def test_batch_processing_works(self) -> None:
        """Multiple books should be processed and all reported in metadata."""
        from litmatch.defs.assets.embedding import book_description_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        for i in range(5):
            _seed_book(conn_str, f"Batch Book {i}", f"Description for batch book {i}.")

        mock_st = _make_fake_st(5)
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch("sentence_transformers.SentenceTransformer", return_value=mock_st):
            result = book_description_embeddings(context)

        assert result.metadata["books_embedded"] == 5

    def test_emits_correct_metadata(self) -> None:
        """MaterializeResult should include books_embedded, books_skipped, model_name, dimensions."""
        from litmatch.defs.assets.embedding import book_description_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_book(conn_str, "Meta Book", "Good description.")
        _seed_book(conn_str, "Skip Book", "")  # will be skipped

        mock_st = _make_fake_st(1)
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch("sentence_transformers.SentenceTransformer", return_value=mock_st):
            result = book_description_embeddings(context)

        assert "books_embedded" in result.metadata
        assert "books_skipped" in result.metadata
        assert "model_name" in result.metadata
        assert "dimensions" in result.metadata
        assert result.metadata["books_embedded"] == 1
        assert result.metadata["books_skipped"] == 1

    def test_empty_database_returns_zero(self) -> None:
        """When there are no books, the asset returns zero embedded."""
        from litmatch.defs.assets.embedding import book_description_embeddings
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

        with patch("sentence_transformers.SentenceTransformer", return_value=mock_st):
            result = book_description_embeddings(context)

        mock_st.encode.assert_not_called()
        assert result.metadata["books_embedded"] == 0

    def test_idempotent_second_run_embeds_nothing(self) -> None:
        """Running the asset twice should embed descriptions only on first run."""
        from litmatch.defs.assets.embedding import book_description_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_book(conn_str, "Idempotent Book", "Description to embed.")

        mock_st = _make_fake_st(1)
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        # First run: embeds all
        context1 = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )
        with patch("sentence_transformers.SentenceTransformer", return_value=mock_st):
            result1 = book_description_embeddings(context1)
        assert result1.metadata["books_embedded"] == 1

        mock_st.encode.reset_mock()

        # Second run: embeds nothing
        context2 = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )
        with patch("sentence_transformers.SentenceTransformer", return_value=mock_st):
            result2 = book_description_embeddings(context2)
        assert result2.metadata["books_embedded"] == 0
        mock_st.encode.assert_not_called()

    def test_encode_error_raises_dagster_failure(self) -> None:
        """A RuntimeError from encode() should be wrapped in dg.Failure."""
        from litmatch.defs.assets.embedding import book_description_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_book(conn_str, "Error Book", "A description that will fail.")

        mock_st = MagicMock()
        mock_st.encode.side_effect = RuntimeError("Model error")
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch("sentence_transformers.SentenceTransformer", return_value=mock_st):
            with pytest.raises(dg.Failure):
                book_description_embeddings(context)

    def test_engine_disposed_on_success(self) -> None:
        """Engine should be disposed after successful embedding generation."""
        from litmatch.defs.assets.embedding import book_description_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_book(conn_str, "Dispose Book", "Valid description.")

        mock_st = _make_fake_st(1)
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
            "sentence_transformers.SentenceTransformer", return_value=mock_st
        ), patch(
            "litmatch.defs.assets.embedding.DatabaseResource.get_engine",
            return_value=real_engine,
        ):
            book_description_embeddings(context)

        mock_dispose.assert_called_once()


class TestBookDescriptionEmbeddingsDimensionValidation:
    """Tests that book_description_embeddings raises dg.Failure for wrong-dim embeddings."""

    def test_wrong_dim_raises_dagster_failure(self) -> None:
        """book_description_embeddings should raise dg.Failure for wrong embedding dims."""
        from litmatch.defs.assets.embedding import book_description_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_book(conn_str, "Dim Validation Book", "A valid description for testing.")

        # Return 256-dim embeddings instead of expected 384-dim
        mock_st = MagicMock()
        wrong_dim_emb = np.random.RandomState(1).rand(1, 256).astype(np.float32)
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
                book_description_embeddings(context)

    def test_correct_dim_does_not_raise(self) -> None:
        """book_description_embeddings should NOT raise for correct 384-dim embeddings."""
        from litmatch.defs.assets.embedding import book_description_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_book(conn_str, "Valid Dim Book", "A valid description for testing.")

        mock_st = _make_fake_st(1, dims=384)
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch("sentence_transformers.SentenceTransformer", return_value=mock_st):
            result = book_description_embeddings(context)

        assert result.metadata["books_embedded"] == 1


class TestBookDescriptionEmbeddingsN1Elimination:
    """Tests that book_description_embeddings uses batch pre-fetch, not per-row SELECT."""

    def test_batch_prefetch_replaces_per_row_select(self) -> None:
        """The asset should use a single batch SELECT for existing IDs per batch,
        not one SELECT per book."""
        from litmatch.defs.assets.embedding import book_description_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource
        from sqlmodel import Session as SMSession

        conn_str, _ = _make_test_db()
        num_books = 5
        for i in range(num_books):
            _seed_book(conn_str, f"N1 Test Book {i}", f"Description {i}.")

        mock_st = _make_fake_st(num_books, dims=384)
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        execute_calls: list[str] = []

        original_execute = SMSession.execute

        def tracking_execute(self, stmt, *args, **kwargs):
            stmt_str = str(stmt)
            execute_calls.append(stmt_str)
            return original_execute(self, stmt, *args, **kwargs)

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch("sentence_transformers.SentenceTransformer", return_value=mock_st), \
             patch.object(SMSession, "execute", tracking_execute):
            result = book_description_embeddings(context)

        assert result.metadata["books_embedded"] == num_books

        # Count SELECT statements on book_embeddings that check existence by book_id.
        # With N+1 pattern: would be num_books individual SELECTs (one per book).
        # With batch pre-fetch: exactly 1 SELECT using IN clause (no LEFT OUTER JOIN).
        # Filter: SELECT from book_embeddings using IN but NOT a LEFT OUTER JOIN query.
        book_emb_selects = [
            c for c in execute_calls
            if "book_embeddings" in c.lower()
            and "select" in c.lower()
            and "in" in c.lower()
            and "left outer join" not in c.lower()
            and "outer join" not in c.lower()
        ]
        # There should be exactly 1 batch-prefetch SELECT (not num_books individual ones)
        assert len(book_emb_selects) == 1, (
            f"Expected 1 batch SELECT on book_embeddings, got {len(book_emb_selects)}. "
            "N+1 pattern may not have been eliminated. "
            f"Matching queries: {book_emb_selects}"
        )
