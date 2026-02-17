"""Unit tests for the book_genre_embeddings Dagster asset.

Tests the asset that computes per-book genre embeddings by averaging
the linked genre embeddings. Uses in-memory SQLite for database tests.

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


def _seed_book(conn_str: str, title: str) -> int:
    """Insert a book. Returns book_id."""
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
            description=f"Description for {title}.",
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


def _seed_genre(conn_str: str, name: str, embedding: list[float] | None = None) -> int:
    """Insert a genre with optional embedding. Returns genre_id."""
    from backend.db.models import Genre

    engine = create_engine(conn_str)

    with Session(engine) as session:
        genre = Genre(name=name)
        session.add(genre)
        session.flush()
        genre_id = genre.id
        session.commit()

    if embedding is not None:
        with Session(engine) as session:
            session.execute(
                sa_text("UPDATE genre SET embedding = :emb WHERE id = :id"),
                {"emb": json.dumps(embedding), "id": genre_id},
            )
            session.commit()

    engine.dispose()
    return genre_id


def _link_book_genre(conn_str: str, book_id: int, genre_id: int) -> None:
    """Create a BookGenreLink row."""
    from backend.db.models import BookGenreLink

    engine = create_engine(conn_str)
    with Session(engine) as session:
        link = BookGenreLink(book_id=book_id, genre_id=genre_id)
        session.add(link)
        session.commit()
    engine.dispose()


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


def _get_genre_embedding(conn_str: str, book_id: int) -> str | None:
    """Read the raw genre_embedding from the book_embeddings table."""
    engine = create_engine(conn_str)
    with Session(engine) as session:
        result = session.execute(
            sa_text(
                "SELECT genre_embedding FROM book_embeddings WHERE book_id = :id"
            ),
            {"id": book_id},
        ).one_or_none()
    engine.dispose()
    return result[0] if result else None


class TestBookGenreEmbeddingsAssetDefinition:
    """Tests that the book_genre_embeddings asset is properly defined."""

    def test_asset_exists(self) -> None:
        from litmatch.defs.assets.embedding import book_genre_embeddings

        assert book_genre_embeddings is not None

    def test_asset_is_dagster_asset(self) -> None:
        from litmatch.defs.assets.embedding import book_genre_embeddings

        assert hasattr(book_genre_embeddings, "op")

    def test_asset_depends_on_genre_embeddings(self) -> None:
        """book_genre_embeddings should declare genre_embeddings as a dependency."""
        from litmatch.defs.assets.embedding import book_genre_embeddings

        dep_keys = book_genre_embeddings.asset_deps[book_genre_embeddings.key]
        assert dg.AssetKey("genre_embeddings") in dep_keys


class TestBookGenreEmbeddingsAssetLogic:
    """Tests for the book_genre_embeddings asset logic."""

    def test_computes_mean_of_genre_embeddings_correctly(self) -> None:
        """The asset should compute element-wise mean of genre embeddings for a book."""
        from litmatch.defs.assets.embedding import book_genre_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        dim = 384

        # Use known embeddings: e1=[1,0,...] and e2=[0,1,...], expected mean=[0.5,0.5,...]
        emb1 = [0.0] * dim
        emb1[0] = 1.0
        emb2 = [0.0] * dim
        emb2[1] = 1.0

        book_id = _seed_book(conn_str, "Mean Genre Book")
        g1 = _seed_genre(conn_str, "Genre A", emb1)
        g2 = _seed_genre(conn_str, "Genre B", emb2)
        _link_book_genre(conn_str, book_id, g1)
        _link_book_genre(conn_str, book_id, g2)

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        result = book_genre_embeddings(context)

        assert isinstance(result, dg.MaterializeResult)
        assert result.metadata["books_computed"] == 1

        stored_raw = _get_genre_embedding(conn_str, book_id)
        assert stored_raw is not None
        stored = json.loads(stored_raw)
        expected = np.mean([emb1, emb2], axis=0).tolist()
        np.testing.assert_allclose(stored, expected, rtol=1e-5)

    def test_skips_books_with_no_genres(self) -> None:
        """Books without any genre links should be skipped."""
        from litmatch.defs.assets.embedding import book_genre_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        _seed_book(conn_str, "No Genres Book")  # no genre links

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        result = book_genre_embeddings(context)

        assert result.metadata["books_computed"] == 0

    def test_skips_books_where_genres_have_no_embeddings(self) -> None:
        """Books with genres that have no embeddings yet should be skipped."""
        from litmatch.defs.assets.embedding import book_genre_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book_id = _seed_book(conn_str, "Unembedded Genre Book")
        genre_id = _seed_genre(conn_str, "Empty Genre")  # no embedding set
        _link_book_genre(conn_str, book_id, genre_id)

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        result = book_genre_embeddings(context)

        assert result.metadata["books_computed"] == 0

    def test_creates_book_embedding_row_when_none_exists(self) -> None:
        """The asset should INSERT a new BookEmbedding row when none exists."""
        from litmatch.defs.assets.embedding import book_genre_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book_id = _seed_book(conn_str, "New BE Row Book")
        genre_id = _seed_genre(conn_str, "Mystery Genre", [0.2] * 384)
        _link_book_genre(conn_str, book_id, genre_id)

        # No BookEmbedding row exists yet
        assert _get_genre_embedding(conn_str, book_id) is None

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        result = book_genre_embeddings(context)

        assert result.metadata["books_computed"] == 1
        stored = _get_genre_embedding(conn_str, book_id)
        assert stored is not None

    def test_updates_existing_book_embedding_row(self) -> None:
        """The asset should UPDATE genre_embedding on an existing BookEmbedding."""
        from litmatch.defs.assets.embedding import book_genre_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book_id = _seed_book(conn_str, "Existing BE Book")
        genre_id = _seed_genre(conn_str, "Sci-Fi Genre", [0.3] * 384)
        _link_book_genre(conn_str, book_id, genre_id)
        _seed_book_embedding(conn_str, book_id)  # existing BookEmbedding with NULL genre_embedding

        # Verify genre_embedding is NULL before asset runs
        assert _get_genre_embedding(conn_str, book_id) is None

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        result = book_genre_embeddings(context)

        assert result.metadata["books_computed"] == 1
        stored = _get_genre_embedding(conn_str, book_id)
        assert stored is not None

    def test_handles_single_genre_per_book(self) -> None:
        """A book with one genre gets that genre's embedding directly."""
        from litmatch.defs.assets.embedding import book_genre_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        emb = [0.7] * 384
        book_id = _seed_book(conn_str, "Single Genre Book")
        genre_id = _seed_genre(conn_str, "Single Genre", emb)
        _link_book_genre(conn_str, book_id, genre_id)

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        result = book_genre_embeddings(context)

        assert result.metadata["books_computed"] == 1
        stored_raw = _get_genre_embedding(conn_str, book_id)
        assert stored_raw is not None
        stored = json.loads(stored_raw)
        np.testing.assert_allclose(stored, emb, rtol=1e-5)

    def test_handles_empty_database(self) -> None:
        """When there are no books, the asset returns zero computed."""
        from litmatch.defs.assets.embedding import book_genre_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        result = book_genre_embeddings(context)

        assert result.metadata["books_computed"] == 0

    def test_computes_for_multiple_books(self) -> None:
        """The asset should compute genre embeddings for multiple books."""
        from litmatch.defs.assets.embedding import book_genre_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book1 = _seed_book(conn_str, "Multi Book One")
        book2 = _seed_book(conn_str, "Multi Book Two")
        g1 = _seed_genre(conn_str, "Fantasy", [0.1] * 384)
        g2 = _seed_genre(conn_str, "Horror Multi", [0.9] * 384)
        _link_book_genre(conn_str, book1, g1)
        _link_book_genre(conn_str, book2, g2)

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        result = book_genre_embeddings(context)

        assert result.metadata["books_computed"] == 2

    def test_idempotent_second_run_computes_nothing(self) -> None:
        """Running the asset twice should compute genre embeddings only on first run."""
        from litmatch.defs.assets.embedding import book_genre_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book_id = _seed_book(conn_str, "Idempotent Genre Book")
        genre_id = _seed_genre(conn_str, "Idempotent Genre", [0.5] * 384)
        _link_book_genre(conn_str, book_id, genre_id)

        db_resource = DatabaseResource(connection_string=conn_str)

        context1 = dg.build_asset_context(resources={"database": db_resource})
        result1 = book_genre_embeddings(context1)
        assert result1.metadata["books_computed"] == 1

        context2 = dg.build_asset_context(resources={"database": db_resource})
        result2 = book_genre_embeddings(context2)
        assert result2.metadata["books_computed"] == 0

    def test_engine_disposed_on_success(self) -> None:
        """Engine should be disposed after successful computation."""
        from litmatch.defs.assets.embedding import book_genre_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book_id = _seed_book(conn_str, "Dispose Genre Book")
        genre_id = _seed_genre(conn_str, "Dispose Genre", [0.4] * 384)
        _link_book_genre(conn_str, book_id, genre_id)

        real_engine = create_engine(conn_str)
        mock_dispose = MagicMock(wraps=real_engine.dispose)
        real_engine.dispose = mock_dispose

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        with patch(
            "litmatch.defs.assets.embedding.DatabaseResource.get_engine",
            return_value=real_engine,
        ):
            book_genre_embeddings(context)

        mock_dispose.assert_called_once()

    def test_engine_disposed_on_empty_database(self) -> None:
        """Engine should be disposed even when no books are eligible."""
        from litmatch.defs.assets.embedding import book_genre_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()

        real_engine = create_engine(conn_str)
        mock_dispose = MagicMock(wraps=real_engine.dispose)
        real_engine.dispose = mock_dispose

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        with patch(
            "litmatch.defs.assets.embedding.DatabaseResource.get_engine",
            return_value=real_engine,
        ):
            book_genre_embeddings(context)

        mock_dispose.assert_called_once()


class TestBookGenreEmbeddingsN1Elimination:
    """Tests that book_genre_embeddings uses a batch pre-fetch for existence checks."""

    def test_batch_prefetch_replaces_per_row_select(self) -> None:
        """The asset should do one batch SELECT for existing book IDs, not N individual ones."""
        from litmatch.defs.assets.embedding import book_genre_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from sqlmodel import Session as SMSession

        conn_str, _ = _make_test_db()
        num_books = 5
        genre_emb = [0.1] * 384

        for i in range(num_books):
            book_id = _seed_book(conn_str, f"N1 Genre Book {i}")
            genre_id = _seed_genre(conn_str, f"N1 Genre {i}", genre_emb)
            _link_book_genre(conn_str, book_id, genre_id)

        db_resource = DatabaseResource(connection_string=conn_str)

        execute_calls: list[str] = []
        original_execute = SMSession.execute

        def tracking_execute(self, stmt, *args, **kwargs):
            stmt_str = str(stmt)
            execute_calls.append(stmt_str)
            return original_execute(self, stmt, *args, **kwargs)

        context = dg.build_asset_context(resources={"database": db_resource})

        with patch.object(SMSession, "execute", tracking_execute):
            result = book_genre_embeddings(context)

        assert result.metadata["books_computed"] == num_books

        # With N+1 pattern: would be num_books individual SELECTs per book.
        # With batch pre-fetch: exactly 1 SELECT using IN clause (no LEFT OUTER JOIN).
        # Exclude LEFT OUTER JOIN queries (those are the initial eligible-books query).
        book_emb_selects = [
            c for c in execute_calls
            if "book_embeddings" in c.lower()
            and "select" in c.lower()
            and "in" in c.lower()
            and "left outer join" not in c.lower()
            and "outer join" not in c.lower()
        ]
        assert len(book_emb_selects) == 1, (
            f"Expected 1 batch SELECT on book_embeddings, got {len(book_emb_selects)}. "
            "N+1 pattern may not have been eliminated. "
            f"Matching queries: {book_emb_selects}"
        )
