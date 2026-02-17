"""Unit tests for the genre_embeddings Dagster asset.

Tests the asset that generates embeddings for genre names using
sentence-transformers. Uses in-memory SQLite for database tests and
a patched SentenceTransformer model.

Note: SQLite does not support pgvector's Vector type natively. The
Vector column is created by SQLModel as a generic column in SQLite.
"""
import json
import tempfile
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


def _seed_genres(conn_str: str, names: list[str]) -> list[int]:
    """Insert genre rows into the database. Returns list of genre IDs."""
    from backend.db.models import Genre

    engine = create_engine(conn_str)
    genre_ids: list[int] = []

    with Session(engine) as session:
        for name in names:
            genre = Genre(name=name)
            session.add(genre)
            session.flush()
            genre_ids.append(genre.id)
        session.commit()

    engine.dispose()
    return genre_ids


def _set_genre_embedding(conn_str: str, genre_id: int, emb: list[float]) -> None:
    """Set the embedding for a genre via raw SQL."""
    engine = create_engine(conn_str)
    with Session(engine) as session:
        session.execute(
            sa_text("UPDATE genre SET embedding = :emb WHERE id = :id"),
            {"emb": json.dumps(emb), "id": genre_id},
        )
        session.commit()
    engine.dispose()


def _make_fake_st(num_texts: int, dims: int = 384) -> MagicMock:
    """Create a fake SentenceTransformer that returns deterministic embeddings."""
    fake_embeddings = np.random.RandomState(42).rand(num_texts, dims).astype(np.float32)
    mock_model = MagicMock()
    mock_model.encode.return_value = fake_embeddings
    return mock_model


class TestGenreEmbeddingsAssetDefinition:
    """Tests that the genre_embeddings asset is properly defined."""

    def test_asset_exists(self) -> None:
        from litmatch.defs.assets.embedding import genre_embeddings

        assert genre_embeddings is not None

    def test_asset_is_dagster_asset(self) -> None:
        from litmatch.defs.assets.embedding import genre_embeddings

        assert hasattr(genre_embeddings, "op")

    def test_asset_depends_on_load_books(self) -> None:
        """genre_embeddings should declare load_books as a dependency."""
        from litmatch.defs.assets.embedding import genre_embeddings

        dep_keys = genre_embeddings.asset_deps[genre_embeddings.key]
        assert dg.AssetKey("load_books") in dep_keys


class TestGenreEmbeddingsAssetLogic:
    """Tests for the genre_embeddings asset logic."""

    def test_embeds_all_genres_without_embeddings(self) -> None:
        """The asset should encode all genres that have no embedding yet."""
        from litmatch.defs.assets.embedding import genre_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_genres(conn_str, ["Literary Fiction", "Mystery", "Science Fiction"])

        mock_st = _make_fake_st(3)
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        context = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )

        with patch("sentence_transformers.SentenceTransformer", return_value=mock_st):
            result = genre_embeddings(context)

        mock_st.encode.assert_called_once()
        call_args = mock_st.encode.call_args[0][0]
        assert len(call_args) == 3
        assert set(call_args) == {"Literary Fiction", "Mystery", "Science Fiction"}

        assert isinstance(result, dg.MaterializeResult)
        assert result.metadata["genres_embedded"] == 3

    def test_skips_genres_with_existing_embeddings(self) -> None:
        """The asset should skip genres that already have embeddings (idempotent)."""
        from litmatch.defs.assets.embedding import genre_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        genre_ids = _seed_genres(conn_str, ["Fiction", "Nonfiction", "Poetry"])

        # Give the first genre an embedding already
        _set_genre_embedding(conn_str, genre_ids[0], [0.1] * 384)

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
            result = genre_embeddings(context)

        call_args = mock_st.encode.call_args[0][0]
        assert len(call_args) == 2

        assert isinstance(result, dg.MaterializeResult)
        assert result.metadata["genres_embedded"] == 2

    def test_handles_empty_genre_table(self) -> None:
        """When there are no genres, the asset returns zero embedded."""
        from litmatch.defs.assets.embedding import genre_embeddings
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
            result = genre_embeddings(context)

        mock_st.encode.assert_not_called()
        assert isinstance(result, dg.MaterializeResult)
        assert result.metadata["genres_embedded"] == 0

    def test_all_genres_already_embedded_returns_zero(self) -> None:
        """When all genres already have embeddings, returns zero embedded."""
        from litmatch.defs.assets.embedding import genre_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        genre_ids = _seed_genres(conn_str, ["Fiction", "Nonfiction"])
        for gid in genre_ids:
            _set_genre_embedding(conn_str, gid, [0.5] * 384)

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
            result = genre_embeddings(context)

        mock_st.encode.assert_not_called()
        assert result.metadata["genres_embedded"] == 0

    def test_emits_correct_metadata(self) -> None:
        """MaterializeResult metadata should include genres_embedded, model_name, dimensions."""
        from litmatch.defs.assets.embedding import genre_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_genres(conn_str, ["Drama", "Thriller"])

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
            result = genre_embeddings(context)

        assert "genres_embedded" in result.metadata
        assert "model_name" in result.metadata
        assert "dimensions" in result.metadata
        assert result.metadata["model_name"] == "all-MiniLM-L6-v2"
        assert result.metadata["dimensions"] == 384
        assert result.metadata["genres_embedded"] == 2

    def test_writes_embeddings_to_database(self) -> None:
        """The asset should write embeddings back to genre rows."""
        from litmatch.defs.assets.embedding import genre_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource
        from backend.db.models import Genre

        conn_str, _ = _make_test_db()
        _seed_genres(conn_str, ["Horror", "Romance"])

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
            genre_embeddings(context)

        engine = create_engine(conn_str)
        with Session(engine) as session:
            genres = session.exec(select(Genre)).all()
            for genre in genres:
                assert genre.embedding is not None
        engine.dispose()

    def test_idempotent_second_run_embeds_nothing(self) -> None:
        """Running the asset twice should embed genres only on first run."""
        from litmatch.defs.assets.embedding import genre_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_genres(conn_str, ["Biography", "History"])

        mock_st = _make_fake_st(2)
        db_resource = DatabaseResource(connection_string=conn_str)
        emb_resource = EmbeddingModelResource()

        # First run: embeds all genres
        context1 = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )
        with patch("sentence_transformers.SentenceTransformer", return_value=mock_st):
            result1 = genre_embeddings(context1)
        assert result1.metadata["genres_embedded"] == 2

        mock_st.encode.reset_mock()

        # Second run: should embed nothing
        context2 = dg.build_asset_context(
            resources={
                "database": db_resource,
                "embedding_model": emb_resource,
            }
        )
        with patch("sentence_transformers.SentenceTransformer", return_value=mock_st):
            result2 = genre_embeddings(context2)
        assert result2.metadata["genres_embedded"] == 0
        mock_st.encode.assert_not_called()

    def test_encode_error_raises_dagster_failure(self) -> None:
        """A RuntimeError from encode() should be wrapped in dg.Failure."""
        from litmatch.defs.assets.embedding import genre_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_genres(conn_str, ["Action", "Comedy"])

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

        with patch("sentence_transformers.SentenceTransformer", return_value=mock_st):
            with pytest.raises(dg.Failure):
                genre_embeddings(context)

    def test_engine_disposed_on_success(self) -> None:
        """Engine should be disposed after successful embedding generation."""
        from litmatch.defs.assets.embedding import genre_embeddings
        from litmatch.defs.resources.database import DatabaseResource
        from litmatch.defs.resources.embedding_model import EmbeddingModelResource

        conn_str, _ = _make_test_db()
        _seed_genres(conn_str, ["Sports"])

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
            genre_embeddings(context)

        mock_dispose.assert_called_once()

    def test_engine_disposed_on_empty_table(self) -> None:
        """Engine should be disposed even when no genres need embedding."""
        from litmatch.defs.assets.embedding import genre_embeddings
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
            "sentence_transformers.SentenceTransformer", return_value=mock_st
        ), patch(
            "litmatch.defs.assets.embedding.DatabaseResource.get_engine",
            return_value=real_engine,
        ):
            genre_embeddings(context)

        mock_dispose.assert_called_once()
