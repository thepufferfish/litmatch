"""Unit tests for the composite_book_embeddings Dagster asset.

Tests the asset that builds 1152-dim composite embeddings by concatenating
L2-normalized sub-vectors: [review(384) | description(384) | genre(384)].

Key invariants under test:
  - Each sub-vector is L2-normalized independently before concatenation.
  - Missing signals are zero-padded (384-dim zeros).
  - The 1152-dim result is NOT further normalized.
  - Norms reflect signal count: 3-sig≈sqrt(3), 2-sig≈sqrt(2), 1-sig≈1.
  - force_recompute=True reprocesses rows with existing embeddings.

Uses in-memory SQLite for database tests.
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


_DIM = 384
_COMPOSITE_DIM = 1152


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
    """Insert a minimal book. Returns book_id."""
    from backend.db.models import Author, Book, Publisher

    engine = create_engine(conn_str)

    with Session(engine) as session:
        author = Author(name=f"Author {title}")
        publisher = Publisher(name=f"Publisher {title}")
        session.add(author)
        session.add(publisher)
        session.flush()

        book = Book(
            title=title,
            author=author,
            publisher=publisher,
            publish_date=date(2025, 1, 1),
            description=f"Description {title}.",
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


def _seed_book_embedding_row(
    conn_str: str,
    book_id: int,
    review_emb: list[float] | None = None,
    desc_emb: list[float] | None = None,
    genre_emb: list[float] | None = None,
    composite_emb: list[float] | None = None,
) -> None:
    """Insert a BookEmbedding row with specified sub-embeddings."""
    from backend.db.models import BookEmbedding

    engine = create_engine(conn_str)
    with Session(engine) as session:
        be = BookEmbedding(
            book_id=book_id,
            updated_at=datetime.now(timezone.utc),
        )
        session.add(be)
        session.flush()
        session.commit()

    # Set embeddings via raw SQL (SQLite can't use Vector type directly)
    updates = {}
    if review_emb is not None:
        updates["review_embedding"] = json.dumps(review_emb)
    if desc_emb is not None:
        updates["description_embedding"] = json.dumps(desc_emb)
    if genre_emb is not None:
        updates["genre_embedding"] = json.dumps(genre_emb)
    if composite_emb is not None:
        updates["embedding"] = json.dumps(composite_emb)

    if updates:
        set_clause = ", ".join(f"{col} = :{col}" for col in updates)
        params = {**updates, "book_id": book_id}
        with Session(engine) as session:
            session.execute(
                sa_text(f"UPDATE book_embeddings SET {set_clause} WHERE book_id = :book_id"),
                params,
            )
            session.commit()

    engine.dispose()


def _get_composite_embedding(conn_str: str, book_id: int) -> list[float] | None:
    """Read the composite embedding from book_embeddings. Returns None if not set."""
    engine = create_engine(conn_str)
    with Session(engine) as session:
        result = session.execute(
            sa_text("SELECT embedding FROM book_embeddings WHERE book_id = :id"),
            {"id": book_id},
        ).one_or_none()
    engine.dispose()
    if result is None or result[0] is None:
        return None
    return json.loads(result[0])


def _l2_normalize(vec: np.ndarray) -> np.ndarray:
    """L2-normalize a vector; return unchanged if norm is zero."""
    norm = np.linalg.norm(vec)
    if norm == 0.0:
        return vec
    return vec / norm


def _make_unit_vec(dim: int = _DIM, seed: int = 42) -> list[float]:
    """Create a deterministic non-zero vector."""
    rng = np.random.RandomState(seed)
    v = rng.rand(dim).astype(np.float32)
    return v.tolist()


class TestCompositeEmbeddingsAssetDefinition:
    """Tests that the composite_book_embeddings asset is properly defined."""

    def test_asset_exists(self) -> None:
        from litmatch.defs.assets.embedding import composite_book_embeddings

        assert composite_book_embeddings is not None

    def test_asset_is_dagster_asset(self) -> None:
        from litmatch.defs.assets.embedding import composite_book_embeddings

        assert hasattr(composite_book_embeddings, "op")

    def test_asset_depends_on_book_embeddings(self) -> None:
        from litmatch.defs.assets.embedding import composite_book_embeddings

        dep_keys = composite_book_embeddings.asset_deps[composite_book_embeddings.key]
        assert dg.AssetKey("book_embeddings") in dep_keys

    def test_asset_depends_on_book_description_embeddings(self) -> None:
        from litmatch.defs.assets.embedding import composite_book_embeddings

        dep_keys = composite_book_embeddings.asset_deps[composite_book_embeddings.key]
        assert dg.AssetKey("book_description_embeddings") in dep_keys

    def test_asset_depends_on_book_genre_embeddings(self) -> None:
        from litmatch.defs.assets.embedding import composite_book_embeddings

        dep_keys = composite_book_embeddings.asset_deps[composite_book_embeddings.key]
        assert dg.AssetKey("book_genre_embeddings") in dep_keys


class TestCompositeEmbeddingsSignalCombinations:
    """Tests for different combinations of sub-embedding signals."""

    def test_three_signals_produces_correct_concatenation(self) -> None:
        """All 3 signals: 1152-dim result = [L2(review) | L2(desc) | L2(genre)]."""
        from litmatch.defs.assets.embedding import composite_book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book_id = _seed_book(conn_str, "Three Signal Book")

        review_v = _make_unit_vec(seed=1)
        desc_v = _make_unit_vec(seed=2)
        genre_v = _make_unit_vec(seed=3)

        _seed_book_embedding_row(conn_str, book_id, review_v, desc_v, genre_v)

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        result = composite_book_embeddings(context)

        assert result.metadata["total_computed"] == 1
        assert result.metadata["three_signal"] == 1

        stored = _get_composite_embedding(conn_str, book_id)
        assert stored is not None
        assert len(stored) == _COMPOSITE_DIM

        # Verify concatenation order and L2-normalization of sub-vectors
        expected_review = _l2_normalize(np.array(review_v, dtype=np.float32))
        expected_desc = _l2_normalize(np.array(desc_v, dtype=np.float32))
        expected_genre = _l2_normalize(np.array(genre_v, dtype=np.float32))
        expected = np.concatenate([expected_review, expected_desc, expected_genre])

        np.testing.assert_allclose(stored, expected.tolist(), rtol=1e-5)

    def test_two_signals_missing_review_zero_pads_review_slot(self) -> None:
        """2 signals (desc + genre): review slot is zero-padded, result is 1152-dim."""
        from litmatch.defs.assets.embedding import composite_book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book_id = _seed_book(conn_str, "Desc Genre Book")

        desc_v = _make_unit_vec(seed=10)
        genre_v = _make_unit_vec(seed=11)

        _seed_book_embedding_row(conn_str, book_id, None, desc_v, genre_v)

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        result = composite_book_embeddings(context)

        assert result.metadata["total_computed"] == 1
        assert result.metadata["two_signal"] == 1

        stored = _get_composite_embedding(conn_str, book_id)
        assert stored is not None
        assert len(stored) == _COMPOSITE_DIM

        # review slot should be zeros
        stored_arr = np.array(stored)
        np.testing.assert_allclose(stored_arr[:384], np.zeros(384), atol=1e-6)

        # desc and genre should be L2-normalized
        expected_desc = _l2_normalize(np.array(desc_v, dtype=np.float32))
        expected_genre = _l2_normalize(np.array(genre_v, dtype=np.float32))
        np.testing.assert_allclose(stored_arr[384:768], expected_desc, rtol=1e-5)
        np.testing.assert_allclose(stored_arr[768:], expected_genre, rtol=1e-5)

    def test_two_signals_missing_description_zero_pads_desc_slot(self) -> None:
        """2 signals (review + genre): description slot is zero-padded."""
        from litmatch.defs.assets.embedding import composite_book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book_id = _seed_book(conn_str, "Review Genre Book")

        review_v = _make_unit_vec(seed=20)
        genre_v = _make_unit_vec(seed=21)

        _seed_book_embedding_row(conn_str, book_id, review_v, None, genre_v)

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        result = composite_book_embeddings(context)

        assert result.metadata["two_signal"] == 1

        stored = _get_composite_embedding(conn_str, book_id)
        stored_arr = np.array(stored)

        # description slot should be zeros
        np.testing.assert_allclose(stored_arr[384:768], np.zeros(384), atol=1e-6)

        expected_review = _l2_normalize(np.array(review_v, dtype=np.float32))
        expected_genre = _l2_normalize(np.array(genre_v, dtype=np.float32))
        np.testing.assert_allclose(stored_arr[:384], expected_review, rtol=1e-5)
        np.testing.assert_allclose(stored_arr[768:], expected_genre, rtol=1e-5)

    def test_one_signal_genre_only_zero_pads_review_and_desc(self) -> None:
        """1 signal (genre only): review and description slots are zero-padded."""
        from litmatch.defs.assets.embedding import composite_book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book_id = _seed_book(conn_str, "Genre Only Book")

        genre_v = _make_unit_vec(seed=30)
        _seed_book_embedding_row(conn_str, book_id, None, None, genre_v)

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        result = composite_book_embeddings(context)

        assert result.metadata["one_signal"] == 1

        stored = _get_composite_embedding(conn_str, book_id)
        assert stored is not None
        assert len(stored) == _COMPOSITE_DIM

        stored_arr = np.array(stored)
        # review and description slots should be zeros
        np.testing.assert_allclose(stored_arr[:384], np.zeros(384), atol=1e-6)
        np.testing.assert_allclose(stored_arr[384:768], np.zeros(384), atol=1e-6)

        expected_genre = _l2_normalize(np.array(genre_v, dtype=np.float32))
        np.testing.assert_allclose(stored_arr[768:], expected_genre, rtol=1e-5)

    def test_zero_signals_skips_row(self) -> None:
        """0 signals: row is skipped, embedding stays NULL."""
        from litmatch.defs.assets.embedding import composite_book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book_id = _seed_book(conn_str, "Zero Signal Book")
        _seed_book_embedding_row(conn_str, book_id, None, None, None)

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        result = composite_book_embeddings(context)

        assert result.metadata["skipped_no_signal"] == 1
        assert result.metadata["total_computed"] == 0

        stored = _get_composite_embedding(conn_str, book_id)
        assert stored is None


class TestCompositeEmbeddingsNormalization:
    """Tests for L2-normalization behavior of sub-vectors."""

    def test_each_sub_vector_is_l2_normalized(self) -> None:
        """Each non-null sub-vector should be L2-normalized before concatenation."""
        from litmatch.defs.assets.embedding import composite_book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book_id = _seed_book(conn_str, "Norm Check Book")

        # Use vectors with different magnitudes
        review_v = [2.0] * _DIM   # magnitude != 1
        desc_v = [3.0] * _DIM
        genre_v = [5.0] * _DIM

        _seed_book_embedding_row(conn_str, book_id, review_v, desc_v, genre_v)

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        composite_book_embeddings(context)

        stored = _get_composite_embedding(conn_str, book_id)
        stored_arr = np.array(stored)

        # Each 384-dim block should have norm == 1.0
        review_block_norm = np.linalg.norm(stored_arr[:384])
        desc_block_norm = np.linalg.norm(stored_arr[384:768])
        genre_block_norm = np.linalg.norm(stored_arr[768:])

        np.testing.assert_allclose(review_block_norm, 1.0, rtol=1e-5)
        np.testing.assert_allclose(desc_block_norm, 1.0, rtol=1e-5)
        np.testing.assert_allclose(genre_block_norm, 1.0, rtol=1e-5)

    def test_final_composite_is_not_l2_normalized(self) -> None:
        """The 1152-dim composite vector should NOT be L2-normalized."""
        from litmatch.defs.assets.embedding import composite_book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book_id = _seed_book(conn_str, "No Final Norm Book")

        review_v = _make_unit_vec(seed=50)
        desc_v = _make_unit_vec(seed=51)
        genre_v = _make_unit_vec(seed=52)
        _seed_book_embedding_row(conn_str, book_id, review_v, desc_v, genre_v)

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        composite_book_embeddings(context)

        stored = _get_composite_embedding(conn_str, book_id)
        stored_arr = np.array(stored)
        total_norm = np.linalg.norm(stored_arr)

        # With 3 signals, norm should be ≈ sqrt(3), not 1.0
        assert total_norm > 1.5, (
            f"Composite norm {total_norm:.4f} suggests final normalization occurred"
        )

    def test_three_signal_norm_approximately_sqrt3(self) -> None:
        """3 signals → composite norm ≈ sqrt(3) ≈ 1.73."""
        from litmatch.defs.assets.embedding import composite_book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book_id = _seed_book(conn_str, "Sqrt3 Book")

        review_v = _make_unit_vec(seed=60)
        desc_v = _make_unit_vec(seed=61)
        genre_v = _make_unit_vec(seed=62)
        _seed_book_embedding_row(conn_str, book_id, review_v, desc_v, genre_v)

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        composite_book_embeddings(context)

        stored = np.array(_get_composite_embedding(conn_str, book_id))
        total_norm = np.linalg.norm(stored)
        np.testing.assert_allclose(total_norm, np.sqrt(3), rtol=1e-3)

    def test_two_signal_norm_approximately_sqrt2(self) -> None:
        """2 signals → composite norm ≈ sqrt(2) ≈ 1.41."""
        from litmatch.defs.assets.embedding import composite_book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book_id = _seed_book(conn_str, "Sqrt2 Book")

        review_v = _make_unit_vec(seed=70)
        genre_v = _make_unit_vec(seed=71)
        _seed_book_embedding_row(conn_str, book_id, review_v, None, genre_v)

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        composite_book_embeddings(context)

        stored = np.array(_get_composite_embedding(conn_str, book_id))
        total_norm = np.linalg.norm(stored)
        np.testing.assert_allclose(total_norm, np.sqrt(2), rtol=1e-3)

    def test_one_signal_norm_approximately_one(self) -> None:
        """1 signal → composite norm ≈ 1.0."""
        from litmatch.defs.assets.embedding import composite_book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book_id = _seed_book(conn_str, "Norm1 Book")

        desc_v = _make_unit_vec(seed=80)
        _seed_book_embedding_row(conn_str, book_id, None, desc_v, None)

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        composite_book_embeddings(context)

        stored = np.array(_get_composite_embedding(conn_str, book_id))
        total_norm = np.linalg.norm(stored)
        np.testing.assert_allclose(total_norm, 1.0, rtol=1e-3)


class TestCompositeEmbeddingsConcatenationOrder:
    """Tests for the fixed concatenation order: review | description | genre."""

    def test_concatenation_order_review_desc_genre(self) -> None:
        """Verify: dims 0-383=review, 384-767=description, 768-1151=genre."""
        from litmatch.defs.assets.embedding import composite_book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book_id = _seed_book(conn_str, "Order Test Book")

        # Use identity-like vectors in the first dimension so we can identify slots
        review_v = [1.0] + [0.0] * (_DIM - 1)   # dominant at index 0
        desc_v = [0.0] * _DIM
        desc_v[1] = 1.0                           # dominant at index 1
        genre_v = [0.0] * _DIM
        genre_v[2] = 1.0                          # dominant at index 2

        _seed_book_embedding_row(conn_str, book_id, review_v, desc_v, genre_v)

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        composite_book_embeddings(context)

        stored = np.array(_get_composite_embedding(conn_str, book_id))

        # Review block: first element should be 1.0 (already unit vector)
        np.testing.assert_allclose(stored[0], 1.0, rtol=1e-5)
        np.testing.assert_allclose(stored[1], 0.0, atol=1e-6)
        np.testing.assert_allclose(stored[2], 0.0, atol=1e-6)

        # Description block: second element relative to block start should be 1.0
        np.testing.assert_allclose(stored[384 + 0], 0.0, atol=1e-6)
        np.testing.assert_allclose(stored[384 + 1], 1.0, rtol=1e-5)

        # Genre block: third element relative to block start should be 1.0
        np.testing.assert_allclose(stored[768 + 0], 0.0, atol=1e-6)
        np.testing.assert_allclose(stored[768 + 2], 1.0, rtol=1e-5)

    def test_composite_is_1152_dimensions(self) -> None:
        """The composite embedding must be exactly 1152 dimensions."""
        from litmatch.defs.assets.embedding import composite_book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book_id = _seed_book(conn_str, "Dim Check Book")
        _seed_book_embedding_row(conn_str, book_id, _make_unit_vec(seed=1), _make_unit_vec(seed=2), _make_unit_vec(seed=3))

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        composite_book_embeddings(context)

        stored = _get_composite_embedding(conn_str, book_id)
        assert stored is not None
        assert len(stored) == _COMPOSITE_DIM


class TestCompositeEmbeddingsForceRecompute:
    """Tests for the force_recompute config option."""

    def test_default_skips_rows_with_existing_embedding(self) -> None:
        """Without force_recompute, rows with existing composite embeddings are skipped."""
        from litmatch.defs.assets.embedding import composite_book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book_id = _seed_book(conn_str, "Already Computed Book")

        existing_composite = [0.1] * _COMPOSITE_DIM
        _seed_book_embedding_row(
            conn_str, book_id,
            _make_unit_vec(seed=1), _make_unit_vec(seed=2), _make_unit_vec(seed=3),
            existing_composite,
        )

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        result = composite_book_embeddings(context)

        # Should be skipped since embedding is already set
        assert result.metadata["total_computed"] == 0

    def test_force_recompute_reprocesses_existing_embeddings(self) -> None:
        """With force_recompute=True, rows with existing embeddings are reprocessed."""
        from litmatch.defs.assets.embedding import composite_book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book_id = _seed_book(conn_str, "Force Recompute Book")

        existing_composite = [0.1] * _COMPOSITE_DIM
        review_v = _make_unit_vec(seed=90)
        desc_v = _make_unit_vec(seed=91)
        genre_v = _make_unit_vec(seed=92)
        _seed_book_embedding_row(
            conn_str, book_id, review_v, desc_v, genre_v, existing_composite
        )

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(
            resources={"database": db_resource},
            asset_config={"force_recompute": True},
        )

        result = composite_book_embeddings(context)

        assert result.metadata["total_computed"] == 1

        # Verify the composite was recomputed correctly (not the old [0.1]*1152)
        stored = _get_composite_embedding(conn_str, book_id)
        stored_arr = np.array(stored)
        old_arr = np.array(existing_composite)
        assert not np.allclose(stored_arr, old_arr), (
            "Composite should have been recomputed, not kept as old value"
        )

    def test_force_recompute_false_is_default(self) -> None:
        """Default config (no explicit force_recompute) should not reprocess existing rows."""
        from litmatch.defs.assets.embedding import composite_book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book_id = _seed_book(conn_str, "Default Config Book")

        old_composite = [0.42] * _COMPOSITE_DIM
        _seed_book_embedding_row(
            conn_str, book_id,
            _make_unit_vec(seed=1), _make_unit_vec(seed=2), _make_unit_vec(seed=3),
            old_composite,
        )

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        result = composite_book_embeddings(context)

        assert result.metadata["total_computed"] == 0

        # Old embedding should still be intact
        stored = _get_composite_embedding(conn_str, book_id)
        np.testing.assert_allclose(stored, old_composite, rtol=1e-5)


class TestCompositeEmbeddingsMetadata:
    """Tests for signal count metadata emitted by the asset."""

    def test_emits_signal_count_metadata(self) -> None:
        """MaterializeResult should include total_computed, three_signal, two_signal, one_signal, skipped."""
        from litmatch.defs.assets.embedding import composite_book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()

        # 1 three-signal book
        b1 = _seed_book(conn_str, "3 Signal Meta")
        _seed_book_embedding_row(conn_str, b1, _make_unit_vec(seed=1), _make_unit_vec(seed=2), _make_unit_vec(seed=3))

        # 1 two-signal book
        b2 = _seed_book(conn_str, "2 Signal Meta")
        _seed_book_embedding_row(conn_str, b2, _make_unit_vec(seed=4), None, _make_unit_vec(seed=5))

        # 1 one-signal book
        b3 = _seed_book(conn_str, "1 Signal Meta")
        _seed_book_embedding_row(conn_str, b3, None, None, _make_unit_vec(seed=6))

        # 1 zero-signal book (should be skipped)
        b4 = _seed_book(conn_str, "0 Signal Meta")
        _seed_book_embedding_row(conn_str, b4, None, None, None)

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        result = composite_book_embeddings(context)

        assert result.metadata["total_computed"] == 3
        assert result.metadata["three_signal"] == 1
        assert result.metadata["two_signal"] == 1
        assert result.metadata["one_signal"] == 1
        assert result.metadata["skipped_no_signal"] == 1

    def test_empty_database_returns_zero_metadata(self) -> None:
        """With no BookEmbedding rows, all metadata counts should be zero."""
        from litmatch.defs.assets.embedding import composite_book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        result = composite_book_embeddings(context)

        assert result.metadata["total_computed"] == 0
        assert result.metadata["three_signal"] == 0
        assert result.metadata["two_signal"] == 0
        assert result.metadata["one_signal"] == 0
        assert result.metadata["skipped_no_signal"] == 0


class TestCompositeEmbeddingsEngineDisposal:
    """Tests that the database engine is properly disposed."""

    def test_engine_disposed_on_success(self) -> None:
        """Engine should be disposed after successful computation."""
        from litmatch.defs.assets.embedding import composite_book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book_id = _seed_book(conn_str, "Dispose Composite Book")
        _seed_book_embedding_row(conn_str, book_id, _make_unit_vec(seed=1), _make_unit_vec(seed=2), _make_unit_vec(seed=3))

        real_engine = create_engine(conn_str)
        mock_dispose = MagicMock(wraps=real_engine.dispose)
        real_engine.dispose = mock_dispose

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        with patch(
            "litmatch.defs.assets.embedding.DatabaseResource.get_engine",
            return_value=real_engine,
        ):
            composite_book_embeddings(context)

        mock_dispose.assert_called_once()

    def test_engine_disposed_on_empty_database(self) -> None:
        """Engine should be disposed even when there is nothing to compute."""
        from litmatch.defs.assets.embedding import composite_book_embeddings
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
            composite_book_embeddings(context)

        mock_dispose.assert_called_once()


class TestCompositeEmbeddingsBatchedProcessing:
    """Tests that composite_book_embeddings processes rows in batches."""

    def test_processes_all_rows_across_multiple_batches(self) -> None:
        """With _BATCH_SIZE rows exceeded, all rows should still be processed."""
        from litmatch.defs.assets.embedding import composite_book_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        import litmatch.defs.assets.embedding as emb_module

        conn_str, _ = _make_test_db()

        # Seed 3 books but pretend batch size is 2 to trigger multi-batch processing
        num_books = 3
        book_ids = []
        for i in range(num_books):
            bid = _seed_book(conn_str, f"Batch Process Book {i}")
            _seed_book_embedding_row(
                conn_str, bid,
                _make_unit_vec(seed=i + 1),
                _make_unit_vec(seed=i + 10),
                _make_unit_vec(seed=i + 20),
            )
            book_ids.append(bid)

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        original_batch_size = emb_module._BATCH_SIZE
        try:
            # Override batch size to 2 to force multiple batches with 3 books
            emb_module._BATCH_SIZE = 2
            result = composite_book_embeddings(context)
        finally:
            emb_module._BATCH_SIZE = original_batch_size

        assert result.metadata["total_computed"] == num_books

        # Verify all books got their composite embedding computed
        for bid in book_ids:
            stored = _get_composite_embedding(conn_str, bid)
            assert stored is not None, f"book_id={bid} should have composite embedding"
            assert len(stored) == _COMPOSITE_DIM

    def test_dimension_mismatch_in_composite_raises_failure(self) -> None:
        """composite_book_embeddings should raise dg.Failure when a sub-embedding
        has wrong dimensions."""
        from litmatch.defs.assets.embedding import composite_book_embeddings
        from litmatch.defs.resources.database import DatabaseResource

        conn_str, _ = _make_test_db()
        book_id = _seed_book(conn_str, "Wrong Dim Composite Book")

        # Seed a BookEmbedding row with a wrong-dim review_embedding (128 instead of 384)
        wrong_dim_review = [0.5] * 128
        correct_desc = _make_unit_vec(seed=1)
        correct_genre = _make_unit_vec(seed=2)
        _seed_book_embedding_row(conn_str, book_id, wrong_dim_review, correct_desc, correct_genre)

        db_resource = DatabaseResource(connection_string=conn_str)
        context = dg.build_asset_context(resources={"database": db_resource})

        with pytest.raises(dg.Failure, match="wrong dim"):
            composite_book_embeddings(context)
