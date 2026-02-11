"""Unit tests for the book_embeddings Dagster asset.

Tests the asset that computes per-book embeddings by averaging
review embeddings. Uses in-memory SQLite for database tests.

Note: SQLite does not support pgvector's Vector type natively. The
Vector column is created by SQLModel as a generic column in SQLite.
"""
import json
import tempfile
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import dagster as dg
import numpy as np
import pytest
from sqlalchemy import create_engine, text as sa_text
from sqlmodel import Session, SQLModel, select


def _make_test_db() -> tuple[str, str]:
    """Create a temporary SQLite database with the schema.

    Returns a (connection_string, db_path) tuple.
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


def _seed_book_with_embedded_reviews(
    conn_str: str,
    book_title: str,
    review_count: int = 3,
    embedding_dim: int = 384,
    seed: int = 42,
    is_fiction: bool = True,
) -> tuple[int, list[int], list[list[float]]]:
    """Insert a book with reviews that already have embeddings.

    Returns (book_id, review_ids, embeddings_as_lists).
    """
    from backend.db.models import Author, Book, Critic, Publication, Publisher, Review

    rng = np.random.RandomState(seed)
    engine = create_engine(conn_str)
    review_ids: list[int] = []
    embeddings: list[list[float]] = []

    with Session(engine) as session:
        author = Author(name=f"Author of {book_title}")
        publisher = Publisher(name=f"Publisher of {book_title}")
        session.add(author)
        session.add(publisher)
        session.flush()

        book = Book(
            title=book_title,
            author=author,
            publisher=publisher,
            publish_date=date(2025, 1, 1),
            description=f"Description of {book_title}.",
            url=f"https://bookmarks.reviews/reviews/{book_title.lower().replace(' ', '-')}/",
            cover=None,
            is_fiction=is_fiction,
            last_scraped=datetime(2025, 10, 13, 11, 0, 0),
        )
        session.add(book)
        session.flush()
        book_id = book.id

        critic = Critic(name=f"Critic for {book_title}")
        publication = Publication(name=f"Publication for {book_title}")
        session.add(critic)
        session.add(publication)
        session.flush()

        for i in range(review_count):
            emb = rng.rand(embedding_dim).astype(np.float32).tolist()
            embeddings.append(emb)

            review = Review(
                book_id=book_id,
                critic=critic,
                publication=publication,
                rating=4,
                review=f"Review {i + 1} for {book_title} with enough text.",
                url=f"https://example.com/{book_title.lower().replace(' ', '-')}-review-{i + 1}",
            )
            session.add(review)
            session.flush()
            review_ids.append(review.id)

        session.commit()

    # Set review embeddings via raw SQL (SQLite can't use Vector type directly)
    engine2 = create_engine(conn_str)
    with Session(engine2) as session:
        for rid, emb in zip(review_ids, embeddings):
            session.execute(
                sa_text("UPDATE review SET embedding = :emb WHERE id = :id"),
                {"emb": json.dumps(emb), "id": rid},
            )
        session.commit()
    engine2.dispose()

    engine.dispose()
    return book_id, review_ids, embeddings


def _seed_book_without_reviews(
    conn_str: str,
    book_title: str,
) -> int:
    """Insert a book with no reviews. Returns book_id."""
    from backend.db.models import Author, Book, Publisher

    engine = create_engine(conn_str)

    with Session(engine) as session:
        author = Author(name=f"Author of {book_title}")
        publisher = Publisher(name=f"Publisher of {book_title}")
        session.add(author)
        session.add(publisher)
        session.flush()

        book = Book(
            title=book_title,
            author=author,
            publisher=publisher,
            publish_date=date(2025, 1, 1),
            description=f"Description of {book_title}.",
            url=f"https://bookmarks.reviews/reviews/{book_title.lower().replace(' ', '-')}/",
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


def _seed_book_with_unembedded_reviews(
    conn_str: str,
    book_title: str,
    review_count: int = 2,
) -> tuple[int, list[int]]:
    """Insert a book with reviews that have embedding=None.

    Returns (book_id, review_ids).
    """
    from backend.db.models import Author, Book, Critic, Publication, Publisher, Review

    engine = create_engine(conn_str)
    review_ids: list[int] = []

    with Session(engine) as session:
        author = Author(name=f"Author of {book_title}")
        publisher = Publisher(name=f"Publisher of {book_title}")
        session.add(author)
        session.add(publisher)
        session.flush()

        book = Book(
            title=book_title,
            author=author,
            publisher=publisher,
            publish_date=date(2025, 1, 1),
            description=f"Description of {book_title}.",
            url=f"https://bookmarks.reviews/reviews/{book_title.lower().replace(' ', '-')}/",
            cover=None,
            is_fiction=True,
            last_scraped=datetime(2025, 10, 13, 11, 0, 0),
        )
        session.add(book)
        session.flush()
        book_id = book.id

        critic = Critic(name=f"Critic for {book_title}")
        publication = Publication(name=f"Publication for {book_title}")
        session.add(critic)
        session.add(publication)
        session.flush()

        for i in range(review_count):
            review = Review(
                book_id=book_id,
                critic=critic,
                publication=publication,
                rating=4,
                review=f"Review {i + 1} for {book_title}.",
                url=f"https://example.com/{book_title.lower().replace(' ', '-')}-review-{i + 1}",
            )
            session.add(review)
            session.flush()
            review_ids.append(review.id)

        session.commit()

    engine.dispose()
    return book_id, review_ids


def _get_book_embedding(conn_str: str, book_id: int) -> str | None:
    """Read the raw embedding value from a book row."""
    engine = create_engine(conn_str)
    with Session(engine) as session:
        result = session.execute(
            sa_text("SELECT embedding FROM book WHERE id = :id"),
            {"id": book_id},
        ).one_or_none()
    engine.dispose()
    return result[0] if result else None


class TestBookEmbeddingsAssetDefinition:
    """Tests that the book_embeddings asset is properly defined."""

    def test_asset_exists(self) -> None:
        from litmatch.defs.assets.embedding import book_embeddings

        assert book_embeddings is not None

    def test_asset_is_dagster_asset(self) -> None:
        from litmatch.defs.assets.embedding import book_embeddings

        assert hasattr(book_embeddings, "op")

    def test_asset_depends_on_review_embeddings(self) -> None:
        from litmatch.defs.assets.embedding import book_embeddings

        dep_keys = book_embeddings.asset_deps[book_embeddings.key]
        assert dg.AssetKey("review_embeddings") in dep_keys

    def test_asset_does_not_depend_on_load_books(self) -> None:
        """book_embeddings depends on review_embeddings, not load_books directly."""
        from litmatch.defs.assets.embedding import book_embeddings

        dep_keys = book_embeddings.asset_deps[book_embeddings.key]
        assert dg.AssetKey("load_books") not in dep_keys


class TestBookEmbeddingsAssetLogic:
    """Tests for the book_embeddings asset averaging logic."""

    def test_computes_average_of_review_embeddings(self) -> None:
        """The asset should compute the mean of review embeddings for a book."""
        from litmatch.defs.assets.embedding import book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book_id, _, review_embs = _seed_book_with_embedded_reviews(
            conn_str, "Test Book", review_count=3
        )

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(
            resources={"database": db_resource}
        )

        result = book_embeddings(context)

        assert isinstance(result, dg.MaterializeResult)
        assert result.metadata["books_computed"] == 1

        # Verify the stored embedding is the mean of review embeddings
        stored_raw = _get_book_embedding(conn_str, book_id)
        assert stored_raw is not None

    def test_computes_embeddings_for_multiple_books(self) -> None:
        from litmatch.defs.assets.embedding import book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        _seed_book_with_embedded_reviews(
            conn_str, "Book One", review_count=2, seed=10
        )
        _seed_book_with_embedded_reviews(
            conn_str, "Book Two", review_count=2, seed=20
        )

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(
            resources={"database": db_resource}
        )

        result = book_embeddings(context)

        assert result.metadata["books_computed"] == 2

    def test_skips_books_with_no_reviews(self) -> None:
        from litmatch.defs.assets.embedding import book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        _seed_book_without_reviews(conn_str, "No Reviews Book")
        _seed_book_with_embedded_reviews(
            conn_str, "Has Reviews Book", review_count=2, seed=99
        )

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(
            resources={"database": db_resource}
        )

        result = book_embeddings(context)

        # Only the book with reviews should be computed
        assert result.metadata["books_computed"] == 1

    def test_skips_books_with_unembedded_reviews_only(self) -> None:
        from litmatch.defs.assets.embedding import book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        _seed_book_with_unembedded_reviews(
            conn_str, "Unembedded Reviews Book", review_count=3
        )

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(
            resources={"database": db_resource}
        )

        result = book_embeddings(context)

        assert result.metadata["books_computed"] == 0

    def test_idempotent_second_run(self) -> None:
        """Running the asset twice should compute only on the first run."""
        from litmatch.defs.assets.embedding import book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        _seed_book_with_embedded_reviews(
            conn_str, "Idempotent Book", review_count=2, seed=77
        )

        db_resource = DatabaseResource(connection_string=conn_str)

        context1 = dg.build_asset_context(
            resources={"database": db_resource}
        )
        result1 = book_embeddings(context1)
        assert result1.metadata["books_computed"] == 1

        context2 = dg.build_asset_context(
            resources={"database": db_resource}
        )
        result2 = book_embeddings(context2)
        assert result2.metadata["books_computed"] == 0

    def test_empty_database_returns_zero(self) -> None:
        from litmatch.defs.assets.embedding import book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(
            resources={"database": db_resource}
        )

        result = book_embeddings(context)

        assert result.metadata["books_computed"] == 0

    def test_single_review_embedding_used_directly(self) -> None:
        """A book with one review should get that review's embedding."""
        from litmatch.defs.assets.embedding import book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book_id, _, review_embs = _seed_book_with_embedded_reviews(
            conn_str, "Single Review Book", review_count=1, seed=55
        )

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(
            resources={"database": db_resource}
        )

        result = book_embeddings(context)

        assert result.metadata["books_computed"] == 1

        # The mean of a single vector is the vector itself
        stored_raw = _get_book_embedding(conn_str, book_id)
        assert stored_raw is not None

    def test_metadata_includes_books_computed(self) -> None:
        from litmatch.defs.assets.embedding import book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        _seed_book_with_embedded_reviews(
            conn_str, "Meta Book One", review_count=1, seed=11
        )
        _seed_book_with_embedded_reviews(
            conn_str, "Meta Book Two", review_count=1, seed=22
        )

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(
            resources={"database": db_resource}
        )

        result = book_embeddings(context)

        assert "books_computed" in result.metadata
        assert result.metadata["books_computed"] == 2


class TestBookEmbeddingsEngineDisposal:
    """Tests that the database engine is properly disposed."""

    def test_engine_disposed_on_success(self) -> None:
        from litmatch.defs.assets.embedding import book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        _seed_book_with_embedded_reviews(
            conn_str, "Dispose Success Book", review_count=2, seed=33
        )

        real_engine = create_engine(conn_str)
        mock_dispose = MagicMock(wraps=real_engine.dispose)
        real_engine.dispose = mock_dispose

        db_resource = DatabaseResource(connection_string=conn_str)

        context = dg.build_asset_context(
            resources={"database": db_resource}
        )

        with patch(
            "litmatch.defs.assets.embedding.DatabaseResource.get_engine",
            return_value=real_engine,
        ):
            result = book_embeddings(context)

        mock_dispose.assert_called_once()
        assert isinstance(result, dg.MaterializeResult)

    def test_engine_disposed_on_no_books(self) -> None:
        from litmatch.defs.assets.embedding import book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()

        real_engine = create_engine(conn_str)
        mock_dispose = MagicMock(wraps=real_engine.dispose)
        real_engine.dispose = mock_dispose

        db_resource = DatabaseResource(connection_string=conn_str)

        context = dg.build_asset_context(
            resources={"database": db_resource}
        )

        with patch(
            "litmatch.defs.assets.embedding.DatabaseResource.get_engine",
            return_value=real_engine,
        ):
            book_embeddings(context)

        mock_dispose.assert_called_once()

    def test_engine_disposed_on_error(self) -> None:
        from litmatch.defs.assets.embedding import book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        _seed_book_with_embedded_reviews(
            conn_str, "Dispose Error Book", review_count=2, seed=44
        )

        real_engine = create_engine(conn_str)
        mock_dispose = MagicMock(wraps=real_engine.dispose)
        real_engine.dispose = mock_dispose

        db_resource = DatabaseResource(connection_string=conn_str)

        context = dg.build_asset_context(
            resources={"database": db_resource}
        )

        with patch(
            "litmatch.defs.assets.embedding.DatabaseResource.get_engine",
            return_value=real_engine,
        ), patch("numpy.mean", side_effect=RuntimeError("numpy crash")):
            with pytest.raises(dg.Failure, match="Failed to compute mean"):
                book_embeddings(context)

        mock_dispose.assert_called_once()


class TestBookEmbeddingsAveragingCorrectness:
    """Tests mathematical correctness of the element-wise mean."""

    def test_average_is_element_wise_mean(self) -> None:
        """Verify the asset computes correct element-wise averages."""
        from litmatch.defs.assets.embedding import book_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from backend.db.models import Author, Book, Critic, Publication, Publisher, Review

        conn_str, _ = _make_test_db()
        dim = 384

        # Create known embeddings: [1,0,0,...] and [0,1,0,...], expected mean [0.5,0.5,0,...]
        emb1 = [0.0] * dim
        emb1[0] = 1.0
        emb2 = [0.0] * dim
        emb2[1] = 1.0

        engine = create_engine(conn_str)
        with Session(engine) as session:
            author = Author(name="Mean Test Author")
            publisher = Publisher(name="Mean Test Publisher")
            session.add(author)
            session.add(publisher)
            session.flush()

            book = Book(
                title="Mean Test Book",
                author=author,
                publisher=publisher,
                publish_date=date(2025, 1, 1),
                description="A book for testing mean computation.",
                url="https://bookmarks.reviews/reviews/mean-test/",
                cover=None,
                is_fiction=True,
                last_scraped=datetime(2025, 10, 13, 11, 0, 0),
            )
            session.add(book)
            session.flush()
            book_id = book.id

            critic = Critic(name="Mean Test Critic")
            publication = Publication(name="Mean Test Publication")
            session.add(critic)
            session.add(publication)
            session.flush()

            for i, emb in enumerate([emb1, emb2]):
                review = Review(
                    book_id=book_id,
                    critic=critic,
                    publication=publication,
                    rating=4,
                    review=f"Mean test review {i + 1}.",
                    url=f"https://example.com/mean-test-review-{i + 1}",
                )
                session.add(review)
                session.flush()

            session.commit()

        # Set embeddings via raw SQL
        with Session(engine) as session:
            reviews = session.execute(
                sa_text("SELECT id FROM review WHERE book_id = :bid ORDER BY id"),
                {"bid": book_id},
            ).all()
            for (rid,), emb in zip(reviews, [emb1, emb2]):
                session.execute(
                    sa_text("UPDATE review SET embedding = :emb WHERE id = :id"),
                    {"emb": json.dumps(emb), "id": rid},
                )
            session.commit()
        engine.dispose()

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(
            resources={"database": db_resource}
        )

        result = book_embeddings(context)

        assert result.metadata["books_computed"] == 1

        # Verify the stored embedding is the correct mean
        stored_raw = _get_book_embedding(conn_str, book_id)
        assert stored_raw is not None
        stored = json.loads(stored_raw)
        expected = np.mean([emb1, emb2], axis=0).tolist()
        np.testing.assert_allclose(stored, expected, rtol=1e-5)

    def test_average_of_identical_embeddings_is_same(self) -> None:
        """Mean of identical embeddings should equal the original."""
        from litmatch.defs.assets.embedding import book_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from backend.db.models import Author, Book, Critic, Publication, Publisher, Review

        conn_str, _ = _make_test_db()
        dim = 384
        constant_emb = np.random.RandomState(99).rand(dim).astype(np.float32).tolist()

        engine = create_engine(conn_str)
        with Session(engine) as session:
            author = Author(name="Identical Test Author")
            publisher = Publisher(name="Identical Test Publisher")
            session.add(author)
            session.add(publisher)
            session.flush()

            book = Book(
                title="Identical Emb Book",
                author=author,
                publisher=publisher,
                publish_date=date(2025, 1, 1),
                description="A book for identical embedding test.",
                url="https://bookmarks.reviews/reviews/identical-test/",
                cover=None,
                is_fiction=True,
                last_scraped=datetime(2025, 10, 13, 11, 0, 0),
            )
            session.add(book)
            session.flush()
            book_id = book.id

            critic = Critic(name="Identical Test Critic")
            publication = Publication(name="Identical Test Publication")
            session.add(critic)
            session.add(publication)
            session.flush()

            for i in range(3):
                review = Review(
                    book_id=book_id,
                    critic=critic,
                    publication=publication,
                    rating=4,
                    review=f"Identical test review {i + 1}.",
                    url=f"https://example.com/identical-test-review-{i + 1}",
                )
                session.add(review)
                session.flush()

            session.commit()

        # Set all reviews to the same embedding
        with Session(engine) as session:
            reviews = session.execute(
                sa_text("SELECT id FROM review WHERE book_id = :bid ORDER BY id"),
                {"bid": book_id},
            ).all()
            for (rid,) in reviews:
                session.execute(
                    sa_text("UPDATE review SET embedding = :emb WHERE id = :id"),
                    {"emb": json.dumps(constant_emb), "id": rid},
                )
            session.commit()
        engine.dispose()

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(
            resources={"database": db_resource}
        )

        result = book_embeddings(context)

        assert result.metadata["books_computed"] == 1

        stored_raw = _get_book_embedding(conn_str, book_id)
        assert stored_raw is not None
        stored = json.loads(stored_raw)
        np.testing.assert_allclose(stored, constant_emb, rtol=1e-5)


class TestEmbeddingPipelineJob:
    """Tests for the embedding_pipeline job definition."""

    def test_embedding_pipeline_job_exists(self) -> None:
        from litmatch.defs.jobs import embedding_pipeline

        assert embedding_pipeline is not None
        assert embedding_pipeline.name == "embedding_pipeline"

    def test_embedding_pipeline_includes_both_assets(self) -> None:
        from litmatch.defs.jobs import embedding_pipeline

        selection_str = str(embedding_pipeline.selection)
        assert "review_embeddings" in selection_str
        assert "book_embeddings" in selection_str

    def test_etl_pipeline_includes_book_embeddings(self) -> None:
        from litmatch.defs.jobs import etl_pipeline

        selection_str = str(etl_pipeline.selection)
        assert "book_embeddings" in selection_str

    def test_crawl_job_does_not_include_book_embeddings(self) -> None:
        """The crawl job only selects crawl_books; embeddings run in etl_pipeline."""
        from litmatch.defs.jobs import crawl_job

        selection_str = str(crawl_job.selection)
        assert "book_embeddings" not in selection_str
