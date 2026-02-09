"""Integration tests for Dagster assets.

Tests the full pipeline: extract -> validate -> transform -> load.
Uses Dagster's testing utilities and in-memory SQLite for database tests.
"""
import json
import os
import pytest
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import dagster as dg
from sqlalchemy import create_engine
from sqlmodel import Session, SQLModel, select


def _find_output_value(outputs: list, output_name: str) -> list[dict]:
    """Find an Output with the given name and return its value."""
    for output in outputs:
        if isinstance(output, dg.Output) and output.output_name == output_name:
            return output.value
    raise AssertionError(f"No Output with name '{output_name}' found")


class TestRawBooksAsset:
    """Tests for the raw_books extract asset.

    raw_books declares crawl_books as a dependency via deps=["crawl_books"],
    but can be materialized independently since deps creates a graph-only
    dependency (not requiring IO manager loads).
    """

    def test_extracts_valid_jsonl(self, jsonl_file: str) -> None:
        from litmatch.defs.assets.extract import raw_books
        from litmatch.defs.resources.path import PathResource

        data_dir = os.path.dirname(jsonl_file)

        # raw_books can be materialized without crawl_books being present
        result = dg.materialize_to_memory(
            [raw_books],
            resources={"path": PathResource(raw_data_dir=data_dir)},
        )

        assert result.success
        output = result.output_for_node("raw_books")
        assert len(output) == 2  # Two records in fixture

    def test_handles_malformed_lines(self, jsonl_file_with_bad_line: str) -> None:
        from litmatch.defs.assets.extract import raw_books
        from litmatch.defs.resources.path import PathResource

        data_dir = os.path.dirname(jsonl_file_with_bad_line)
        # Rename the file to books.jsonl so PathResource finds it
        books_path = os.path.join(data_dir, "books.jsonl")
        if not os.path.exists(books_path):
            os.rename(jsonl_file_with_bad_line, books_path)

        result = dg.materialize_to_memory(
            [raw_books],
            resources={"path": PathResource(raw_data_dir=data_dir)},
        )

        assert result.success
        output = result.output_for_node("raw_books")
        assert len(output) == 2  # Two valid lines, one bad line skipped

    def test_file_not_found_raises(self, tmp_path) -> None:
        from litmatch.defs.assets.extract import raw_books
        from litmatch.defs.resources.path import PathResource

        result = dg.materialize_to_memory(
            [raw_books],
            resources={"path": PathResource(raw_data_dir=str(tmp_path / "nonexistent"))},
            raise_on_error=False,
        )

        assert not result.success


class TestValidateRawBooksAsset:
    """Tests for the validate_raw_books multi-asset (direct invocation).

    After the metadata emission refactor, validate_raw_books yields
    Output objects instead of returning a tuple.
    """

    def test_valid_records_pass(self, sample_records: list[dict], tmp_path) -> None:
        from litmatch.defs.assets.validate import validate_raw_books
        from litmatch.defs.resources.path import PathResource

        path_resource = PathResource(raw_data_dir=str(tmp_path))
        context = dg.build_asset_context(resources={"path": path_resource})
        outputs = list(validate_raw_books(context, sample_records))

        valid = _find_output_value(outputs, "validated_books")
        errors = _find_output_value(outputs, "validation_errors")

        assert len(valid) == 2
        assert len(errors) == 0

    def test_invalid_record_captured(self, tmp_path) -> None:
        from litmatch.defs.assets.validate import validate_raw_books
        from litmatch.defs.resources.path import PathResource

        bad_record = {
            "title": "",
            "author": "",
            "publisher": "",
            "publish_date": "",
            "description": "",
            "genres": [],
            "url": "",
            "cover": None,
            "last_scraped": "",
            "reviews": [],
        }

        path_resource = PathResource(raw_data_dir=str(tmp_path))
        context = dg.build_asset_context(resources={"path": path_resource})
        outputs = list(validate_raw_books(context, [bad_record]))

        valid = _find_output_value(outputs, "validated_books")
        errors = _find_output_value(outputs, "validation_errors")

        assert len(valid) == 0
        assert len(errors) == 1
        assert errors[0]["url"] == ""

    def test_invalid_reviews_filtered_but_book_kept(self, tmp_path) -> None:
        from litmatch.defs.assets.validate import validate_raw_books
        from litmatch.defs.resources.path import PathResource

        record = {
            "title": "Good Book",
            "author": "Good Author",
            "publisher": "Publisher",
            "publish_date": "January 1, 2025",
            "description": "Desc.",
            "genres": ["Fiction"],
            "url": "https://bookmarks.reviews/reviews/good/",
            "cover": None,
            "last_scraped": "2025-01-01 00:00:00",
            "reviews": [
                {
                    "critic": "Good Critic",
                    "publication": "FT",
                    "rating": "Rave",
                    "review": "Good review text.",
                    "url": "https://ft.com/good",
                },
                {
                    "critic": "Bad Critic",
                    "publication": "FT",
                    "rating": "InvalidRating",
                    "review": "Bad review.",
                    "url": "https://ft.com/bad",
                },
            ],
        }

        path_resource = PathResource(raw_data_dir=str(tmp_path))
        context = dg.build_asset_context(resources={"path": path_resource})
        outputs = list(validate_raw_books(context, [record]))

        valid = _find_output_value(outputs, "validated_books")

        assert len(valid) == 1
        assert len(valid[0]["reviews"]) == 1  # Bad review filtered out


class TestCleanedBooksAsset:
    """Tests for the cleaned_books transform asset (direct invocation).

    After the metadata emission refactor, cleaned_books returns an
    Output object instead of a plain list.
    """

    def test_transforms_validated_records(self) -> None:
        from litmatch.defs.assets.transform import cleaned_books

        records = [
            {
                "title": "Test Book",
                "author": "Author",
                "publisher": "Publisher",
                "publish_date": "October 7, 2025",
                "description": "Desc.",
                "genres": ["Fiction", "Literary"],
                "url": "https://bookmarks.reviews/reviews/test/",
                "cover": None,
                "last_scraped": "2025-10-13 11:23:31",
                "reviews": [
                    {
                        "critic": "John Self,",
                        "publication": "FT",
                        "rating": "Rave",
                        "review": "Great book.",
                        "url": "https://ft.com/review",
                    }
                ],
            }
        ]

        context = dg.build_asset_context()
        result = cleaned_books(context, records)

        output = result.value if isinstance(result, dg.Output) else result
        assert len(output) == 1
        assert output[0]["publish_date"] == date(2025, 10, 7)
        assert output[0]["is_fiction"] is True
        assert output[0]["reviews"][0]["critic"] == "John Self"
        assert output[0]["reviews"][0]["rating"] == 4

    def test_skips_records_with_transform_errors(self) -> None:
        from litmatch.defs.assets.transform import cleaned_books

        records = [
            {
                "title": "Missing Last Scraped",
                "author": "Author",
                "publisher": "Publisher",
                "publish_date": "January 1, 2025",
                "description": "Desc.",
                "genres": ["Fiction"],
                "url": "https://bookmarks.reviews/reviews/bad/",
                "cover": None,
                # Missing last_scraped entirely -- will cause KeyError
                "reviews": [],
            }
        ]

        context = dg.build_asset_context()
        result = cleaned_books(context, records)

        output = result.value if isinstance(result, dg.Output) else result
        assert len(output) == 0  # Record was skipped


class TestLoadBooksAsset:
    """Tests for the load_books asset with in-memory SQLite.

    Uses a real DatabaseResource with sqlite:///:memory: to satisfy
    Dagster's resource type validation.
    """

    def _make_db_resource(self):
        """Create a DatabaseResource for an in-memory SQLite DB with tables."""
        import backend.db.models  # noqa: F401
        from litmatch.defs.resources.database import DatabaseResource

        # Use a file-based SQLite to share across connections
        import tempfile
        db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = db_file.name
        db_file.close()
        conn_str = f"sqlite:///{db_path}"

        engine = create_engine(conn_str)
        SQLModel.metadata.create_all(engine)
        engine.dispose()

        return DatabaseResource(connection_string=conn_str), conn_str

    def test_loads_transformed_records(self) -> None:
        from litmatch.defs.assets.load import load_books
        from backend.db.models import Book

        db_resource, conn_str = self._make_db_resource()

        records = [
            {
                "title": "Test Book",
                "author": "Test Author",
                "publisher": "Test Publisher",
                "publish_date": date(2025, 1, 1),
                "description": "A test book.",
                "genres": ["Fiction"],
                "url": "https://bookmarks.reviews/reviews/test/",
                "cover": None,
                "last_scraped": datetime(2025, 10, 13, 11, 0, 0),
                "is_fiction": True,
                "reviews": [
                    {
                        "critic": "John Self",
                        "publication": "Financial Times",
                        "rating": 4,
                        "review": "Great.",
                        "url": "https://ft.com/review",
                    }
                ],
            }
        ]

        # Provide resource via context only; Dagster injects it automatically
        context = dg.build_asset_context(resources={"database": db_resource})
        load_books(context, cleaned_books=records)

        engine = create_engine(conn_str)
        with Session(engine) as session:
            books = session.exec(select(Book)).all()
            assert len(books) == 1
            assert books[0].title == "Test Book"

    def test_handles_empty_input(self) -> None:
        from litmatch.defs.assets.load import load_books
        from backend.db.models import Book

        db_resource, conn_str = self._make_db_resource()

        context = dg.build_asset_context(resources={"database": db_resource})
        load_books(context, cleaned_books=[])

        engine = create_engine(conn_str)
        with Session(engine) as session:
            books = session.exec(select(Book)).all()
            assert len(books) == 0

    def test_error_in_one_record_does_not_lose_others(self) -> None:
        """HIGH-4: A failing record should not roll back previously committed records.

        Uses savepoints so each record is independently committed.
        """
        from unittest.mock import patch
        from litmatch.defs.assets.load import load_books
        from backend.db.models import Book
        from sqlalchemy.exc import IntegrityError

        db_resource, conn_str = self._make_db_resource()

        good_record = {
            "title": "Good Book",
            "author": "Good Author",
            "publisher": "Good Publisher",
            "publish_date": date(2025, 1, 1),
            "description": "A good book.",
            "genres": ["Fiction"],
            "url": "https://bookmarks.reviews/reviews/good-book/",
            "cover": None,
            "last_scraped": datetime(2025, 10, 13, 11, 0, 0),
            "is_fiction": True,
            "reviews": [],
        }
        bad_record = {
            "title": "Bad Book",
            "author": "Bad Author",
            "publisher": "Bad Publisher",
            "publish_date": date(2025, 1, 1),
            "description": "A bad book.",
            "genres": ["Fiction"],
            "url": "https://bookmarks.reviews/reviews/bad-book/",
            "cover": None,
            "last_scraped": datetime(2025, 10, 13, 11, 0, 0),
            "is_fiction": True,
            "reviews": [],
        }
        good_record_2 = {
            "title": "Another Good Book",
            "author": "Good Author",
            "publisher": "Good Publisher",
            "publish_date": date(2025, 2, 1),
            "description": "Another good book.",
            "genres": ["Fiction"],
            "url": "https://bookmarks.reviews/reviews/good-book-2/",
            "cover": None,
            "last_scraped": datetime(2025, 10, 13, 11, 0, 0),
            "is_fiction": True,
            "reviews": [],
        }

        # Mock upsert_book to raise SQLAlchemyError on the bad record
        from litmatch.defs.utils import db_operations
        original_upsert = db_operations.upsert_book

        def mock_upsert(session, record):
            if record["url"] == "https://bookmarks.reviews/reviews/bad-book/":
                raise IntegrityError("Constraint violation", params=None, orig=None)
            return original_upsert(session, record)

        context = dg.build_asset_context(resources={"database": db_resource})
        with patch("litmatch.defs.assets.load.upsert_book", side_effect=mock_upsert):
            load_books(context, cleaned_books=[good_record, bad_record, good_record_2])

        engine = create_engine(conn_str)
        with Session(engine) as session:
            books = session.exec(select(Book)).all()
            # Both good records should be saved; bad record should not affect them
            assert len(books) == 2
            titles = {b.title for b in books}
            assert titles == {"Good Book", "Another Good Book"}


class TestDefinitionsFailFast:
    """HIGH-1: definitions.py must fail fast when DATABASE_URL is missing."""

    def test_missing_database_url_raises(self) -> None:
        """If DATABASE_URL is not set, definitions should raise, not use defaults."""
        with patch.dict(os.environ, {}, clear=True):
            # Remove DATABASE_URL and RAW_DATA_DIR if present
            env = os.environ.copy()
            env.pop("DATABASE_URL", None)
            env.pop("RAW_DATA_DIR", None)

            with patch.dict(os.environ, env, clear=True):
                with pytest.raises(
                    EnvironmentError,
                    match="DATABASE_URL",
                ):
                    from litmatch.definitions import _get_database_url
                    _get_database_url()
