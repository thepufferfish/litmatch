"""Tests for Phase 1: Metadata emission on all pipeline assets.

Each asset should emit structured metadata (record counts, validation rates,
timing info) via MaterializeResult or Output metadata for observability.
"""
import json
import os
import tempfile
from collections.abc import Generator
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import dagster as dg
import pytest
from sqlalchemy import create_engine
from sqlmodel import SQLModel

from litmatch.defs.resources.path import PathResource


class TestRawBooksMetadata:
    """raw_books asset should emit metadata: record_count, skipped_count."""

    def test_emits_record_count_metadata(self, jsonl_file: str) -> None:
        """raw_books should include record_count in materialization metadata."""
        from litmatch.defs.assets.extract import raw_books

        data_dir = os.path.dirname(jsonl_file)

        result = dg.materialize_to_memory(
            [raw_books],
            resources={"path": PathResource(raw_data_dir=data_dir)},
        )

        assert result.success
        metadata = _get_metadata(result, "raw_books")
        assert "record_count" in metadata
        assert metadata["record_count"] == 2

    def test_emits_skipped_count_metadata(
        self, jsonl_file_with_bad_line: str, tmp_path
    ) -> None:
        """raw_books should include skipped_count for malformed JSON lines."""
        from litmatch.defs.assets.extract import raw_books

        # Rename the file to books.jsonl so PathResource finds it
        books_path = os.path.join(str(tmp_path), "books.jsonl")
        if not os.path.exists(books_path):
            os.rename(jsonl_file_with_bad_line, books_path)
        data_dir = str(tmp_path)

        result = dg.materialize_to_memory(
            [raw_books],
            resources={"path": PathResource(raw_data_dir=data_dir)},
        )

        assert result.success
        metadata = _get_metadata(result, "raw_books")
        assert "skipped_count" in metadata
        assert metadata["skipped_count"] == 1

    def test_zero_skipped_when_all_valid(self, jsonl_file: str) -> None:
        """skipped_count should be 0 when all lines parse successfully."""
        from litmatch.defs.assets.extract import raw_books

        data_dir = os.path.dirname(jsonl_file)

        result = dg.materialize_to_memory(
            [raw_books],
            resources={"path": PathResource(raw_data_dir=data_dir)},
        )

        assert result.success
        metadata = _get_metadata(result, "raw_books")
        assert metadata["skipped_count"] == 0

    def test_still_returns_parsed_data(self, jsonl_file: str) -> None:
        """raw_books should still produce usable output for downstream assets."""
        from litmatch.defs.assets.extract import raw_books

        data_dir = os.path.dirname(jsonl_file)

        result = dg.materialize_to_memory(
            [raw_books],
            resources={"path": PathResource(raw_data_dir=data_dir)},
        )

        assert result.success
        output = result.output_for_node("raw_books")
        assert isinstance(output, list)
        assert len(output) == 2


class TestValidateRawBooksMetadata:
    """validate_raw_books should emit metadata on both validated_books and validation_errors.

    After the refactor, validate_raw_books yields Output objects instead
    of returning a tuple, enabling metadata attachment.
    """

    @pytest.fixture
    def path_resource(self, tmp_path) -> PathResource:
        """Provide a PathResource with a temporary directory."""
        return PathResource(raw_data_dir=str(tmp_path))

    def test_emits_valid_count_on_validated_books(
        self, sample_records: list[dict], path_resource: PathResource
    ) -> None:
        """validated_books output should include valid_count metadata."""
        from litmatch.defs.assets.validate import validate_raw_books

        context = dg.build_asset_context(resources={"path": path_resource})
        outputs = list(validate_raw_books(context, sample_records))

        validated_output = _find_output(outputs, "validated_books")
        assert validated_output is not None
        assert "valid_count" in validated_output.metadata

    def test_emits_error_count_on_validation_errors(
        self, path_resource: PathResource
    ) -> None:
        """validation_errors output should include error_count metadata."""
        from litmatch.defs.assets.validate import validate_raw_books

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

        context = dg.build_asset_context(resources={"path": path_resource})
        outputs = list(validate_raw_books(context, [bad_record]))

        errors_output = _find_output(outputs, "validation_errors")
        assert errors_output is not None
        metadata = _unwrap_metadata(errors_output.metadata)
        assert "error_count" in metadata
        assert metadata["error_count"] == 1

    def test_emits_validation_rate(
        self, sample_records: list[dict], path_resource: PathResource
    ) -> None:
        """validated_books should include validation_rate (percentage) metadata."""
        from litmatch.defs.assets.validate import validate_raw_books

        context = dg.build_asset_context(resources={"path": path_resource})
        outputs = list(validate_raw_books(context, sample_records))

        validated_output = _find_output(outputs, "validated_books")
        assert validated_output is not None
        metadata = _unwrap_metadata(validated_output.metadata)
        assert "validation_rate" in metadata
        # All 2 records are valid -> 100.0%
        assert metadata["validation_rate"] == 100.0

    def test_emits_total_input_count(
        self, sample_records: list[dict], path_resource: PathResource
    ) -> None:
        """validated_books should include total_input_count metadata."""
        from litmatch.defs.assets.validate import validate_raw_books

        context = dg.build_asset_context(resources={"path": path_resource})
        outputs = list(validate_raw_books(context, sample_records))

        validated_output = _find_output(outputs, "validated_books")
        assert validated_output is not None
        metadata = _unwrap_metadata(validated_output.metadata)
        assert "total_input_count" in metadata
        assert metadata["total_input_count"] == 2

    def test_emits_filtered_reviews_count(
        self, path_resource: PathResource
    ) -> None:
        """validated_books should track how many reviews were filtered out."""
        from litmatch.defs.assets.validate import validate_raw_books

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

        context = dg.build_asset_context(resources={"path": path_resource})
        outputs = list(validate_raw_books(context, [record]))

        validated_output = _find_output(outputs, "validated_books")
        assert validated_output is not None
        metadata = _unwrap_metadata(validated_output.metadata)
        assert "filtered_reviews_count" in metadata
        assert metadata["filtered_reviews_count"] == 1

    def test_yields_correct_data(
        self, sample_records: list[dict], path_resource: PathResource
    ) -> None:
        """validate_raw_books should still yield correct data values."""
        from litmatch.defs.assets.validate import validate_raw_books

        context = dg.build_asset_context(resources={"path": path_resource})
        outputs = list(validate_raw_books(context, sample_records))

        validated_output = _find_output(outputs, "validated_books")
        errors_output = _find_output(outputs, "validation_errors")

        assert validated_output is not None
        assert errors_output is not None
        assert len(validated_output.value) == 2
        assert len(errors_output.value) == 0

    def test_validation_rate_zero_on_empty_input(
        self, path_resource: PathResource
    ) -> None:
        """validation_rate should be 0.0 when no records are provided."""
        from litmatch.defs.assets.validate import validate_raw_books

        context = dg.build_asset_context(resources={"path": path_resource})
        outputs = list(validate_raw_books(context, []))

        validated_output = _find_output(outputs, "validated_books")
        assert validated_output is not None
        metadata = _unwrap_metadata(validated_output.metadata)
        assert metadata["validation_rate"] == 0.0

    def test_is_generator(self, path_resource: PathResource) -> None:
        """After refactoring, validate_raw_books should be a generator function."""
        from litmatch.defs.assets.validate import validate_raw_books

        context = dg.build_asset_context(resources={"path": path_resource})
        result = validate_raw_books(context, [])
        assert isinstance(result, Generator)

    def test_works_via_materialize_to_memory(self, jsonl_file: str) -> None:
        """validate_raw_books should work correctly within Dagster materialization."""
        from litmatch.defs.assets.extract import raw_books
        from litmatch.defs.assets.validate import validate_raw_books

        data_dir = os.path.dirname(jsonl_file)

        result = dg.materialize_to_memory(
            [raw_books, validate_raw_books],
            resources={"path": PathResource(raw_data_dir=data_dir)},
        )

        assert result.success

        # Check metadata on validated_books
        metadata = _get_metadata(result, "validated_books")
        assert metadata["valid_count"] == 2
        assert metadata["validation_rate"] == 100.0

        # Check metadata on validation_errors
        metadata = _get_metadata(result, "validation_errors")
        assert metadata["error_count"] == 0


class TestCleanedBooksMetadata:
    """cleaned_books should emit metadata: transformed_count, skipped_count."""

    def test_emits_transformed_count_via_materialize(self) -> None:
        """cleaned_books should emit transformed_count when materialized."""
        from litmatch.defs.assets.extract import raw_books
        from litmatch.defs.assets.transform import cleaned_books
        from litmatch.defs.assets.validate import validate_raw_books

        records = [
            {
                "title": "Test Book",
                "author": "Author",
                "publisher": "Publisher",
                "publish_date": "October 7, 2025",
                "description": "Desc.",
                "genres": ["Fiction"],
                "url": "https://bookmarks.reviews/reviews/test/",
                "cover": None,
                "last_scraped": "2025-10-13 11:23:31",
                "reviews": [],
            }
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            filepath = os.path.join(tmp_dir, "books.jsonl")
            with open(filepath, "w") as f:
                for r in records:
                    f.write(json.dumps(r) + "\n")

            result = dg.materialize_to_memory(
                [raw_books, validate_raw_books, cleaned_books],
                resources={"path": PathResource(raw_data_dir=tmp_dir)},
            )

        assert result.success
        metadata = _get_metadata(result, "cleaned_books")
        assert "transformed_count" in metadata
        assert metadata["transformed_count"] == 1

    def test_emits_skipped_count_on_transform_errors(self) -> None:
        """cleaned_books should include skipped_count for records that fail transform."""
        from litmatch.defs.assets.extract import raw_books
        from litmatch.defs.assets.transform import cleaned_books
        from litmatch.defs.assets.validate import validate_raw_books

        records = [
            {
                "title": "Good Book",
                "author": "Author",
                "publisher": "Publisher",
                "publish_date": "October 7, 2025",
                "description": "Desc.",
                "genres": ["Fiction"],
                "url": "https://bookmarks.reviews/reviews/good/",
                "cover": None,
                "last_scraped": "2025-10-13 11:23:31",
                "reviews": [],
            },
            {
                "title": "Bad Book",
                "author": "Author",
                "publisher": "Publisher",
                "publish_date": "January 1, 2025",
                "description": "Desc.",
                "genres": ["Fiction"],
                "url": "https://bookmarks.reviews/reviews/bad/",
                "cover": None,
                # Missing last_scraped -> will cause KeyError in transform
                "last_scraped": "bad-format-not-parseable",
                "reviews": [],
            },
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            filepath = os.path.join(tmp_dir, "books.jsonl")
            with open(filepath, "w") as f:
                for r in records:
                    f.write(json.dumps(r) + "\n")

            result = dg.materialize_to_memory(
                [raw_books, validate_raw_books, cleaned_books],
                resources={"path": PathResource(raw_data_dir=tmp_dir)},
            )

        assert result.success
        metadata = _get_metadata(result, "cleaned_books")
        assert "skipped_count" in metadata
        assert metadata["skipped_count"] == 1

    def test_emits_zero_skipped_on_clean_data(self) -> None:
        """skipped_count should be 0 when all records transform successfully."""
        from litmatch.defs.assets.extract import raw_books
        from litmatch.defs.assets.transform import cleaned_books
        from litmatch.defs.assets.validate import validate_raw_books

        records = [
            {
                "title": "Clean Book",
                "author": "Author",
                "publisher": "Publisher",
                "publish_date": "October 7, 2025",
                "description": "Desc.",
                "genres": ["Fiction"],
                "url": "https://bookmarks.reviews/reviews/clean/",
                "cover": None,
                "last_scraped": "2025-10-13 11:23:31",
                "reviews": [],
            }
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            filepath = os.path.join(tmp_dir, "books.jsonl")
            with open(filepath, "w") as f:
                for r in records:
                    f.write(json.dumps(r) + "\n")

            result = dg.materialize_to_memory(
                [raw_books, validate_raw_books, cleaned_books],
                resources={"path": PathResource(raw_data_dir=tmp_dir)},
            )

        assert result.success
        metadata = _get_metadata(result, "cleaned_books")
        assert metadata["skipped_count"] == 0

    def test_direct_invocation_returns_output(self) -> None:
        """cleaned_books should return an Output with metadata on direct call."""
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
        output = cleaned_books(context, records)

        assert isinstance(output, dg.Output)
        assert len(output.value) == 1
        metadata = _unwrap_metadata(output.metadata)
        assert metadata["transformed_count"] == 1
        assert metadata["skipped_count"] == 0


class TestLoadBooksMetadata:
    """load_books should emit metadata: inserted_count, skipped_count, error_count, total_count."""

    def _make_db_resource(self):
        """Create a DatabaseResource for an in-memory SQLite DB with tables."""
        import backend.db.models  # noqa: F401
        from litmatch.defs.resources.database import DatabaseResource

        db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        db_path = db_file.name
        db_file.close()
        conn_str = f"sqlite:///{db_path}"

        engine = create_engine(conn_str)
        SQLModel.metadata.create_all(engine)
        engine.dispose()

        return DatabaseResource(connection_string=conn_str), conn_str

    def test_emits_inserted_count(self) -> None:
        """load_books should include inserted_count in metadata."""
        from litmatch.defs.assets.load import load_books

        db_resource, _ = self._make_db_resource()

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
                "reviews": [],
            }
        ]

        context = dg.build_asset_context(resources={"database": db_resource})
        result = load_books(context, cleaned_books=records)

        assert isinstance(result, dg.MaterializeResult)
        assert result.metadata["inserted_count"] == 1

    def test_emits_skipped_count(self) -> None:
        """load_books should include skipped_count for already-loaded records."""
        from litmatch.defs.assets.load import load_books
        from litmatch.defs.utils.db_operations import upsert_book
        from sqlmodel import Session

        db_resource, conn_str = self._make_db_resource()

        record = {
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
            "reviews": [],
        }

        # Pre-load the record
        engine = create_engine(conn_str)
        with Session(engine) as session:
            upsert_book(session, record)
            session.commit()
        engine.dispose()

        # Load same record again -- should be skipped
        context = dg.build_asset_context(resources={"database": db_resource})
        result = load_books(context, cleaned_books=[record])

        assert isinstance(result, dg.MaterializeResult)
        assert result.metadata["skipped_count"] == 1

    def test_emits_total_count(self) -> None:
        """load_books should include total_count of input records."""
        from litmatch.defs.assets.load import load_books

        db_resource, _ = self._make_db_resource()

        records = [
            {
                "title": f"Test Book {i}",
                "author": "Test Author",
                "publisher": "Test Publisher",
                "publish_date": date(2025, 1, 1),
                "description": "A test book.",
                "genres": ["Fiction"],
                "url": f"https://bookmarks.reviews/reviews/test-{i}/",
                "cover": None,
                "last_scraped": datetime(2025, 10, 13, 11, 0, 0),
                "is_fiction": True,
                "reviews": [],
            }
            for i in range(3)
        ]

        context = dg.build_asset_context(resources={"database": db_resource})
        result = load_books(context, cleaned_books=records)

        assert isinstance(result, dg.MaterializeResult)
        assert result.metadata["total_count"] == 3

    def test_emits_error_count(self) -> None:
        """load_books should include error_count for records that fail to upsert."""
        from unittest.mock import patch
        from litmatch.defs.assets.load import load_books
        from sqlalchemy.exc import OperationalError

        db_resource, _ = self._make_db_resource()

        records = [
            {
                "title": "Good Book",
                "author": "Author",
                "publisher": "Publisher",
                "publish_date": date(2025, 1, 1),
                "description": "Good.",
                "genres": ["Fiction"],
                "url": "https://bookmarks.reviews/reviews/good/",
                "cover": None,
                "last_scraped": datetime(2025, 10, 13, 11, 0, 0),
                "is_fiction": True,
                "reviews": [],
            },
            {
                "title": "Book That Will Fail",
                "author": "Author",
                "publisher": "Publisher",
                "publish_date": date(2025, 1, 1),
                "description": "Will cause DB error.",
                "genres": ["Fiction"],
                "url": "https://bookmarks.reviews/reviews/fail/",
                "cover": None,
                "last_scraped": datetime(2025, 10, 13, 11, 0, 0),
                "is_fiction": True,
                "reviews": [],
            },
        ]

        # Mock upsert_book to raise SQLAlchemyError on the second record
        from litmatch.defs.utils import db_operations
        original_upsert = db_operations.upsert_book
        call_count = [0]

        def mock_upsert(session, record):
            call_count[0] += 1
            if call_count[0] == 2:
                raise OperationalError("Database connection lost", params=None, orig=None)
            return original_upsert(session, record)

        context = dg.build_asset_context(resources={"database": db_resource})
        with patch("litmatch.defs.assets.load.upsert_book", side_effect=mock_upsert):
            result = load_books(context, cleaned_books=records)

        assert isinstance(result, dg.MaterializeResult)
        assert result.metadata["error_count"] == 1


class TestCrawlBooksMetadata:
    """crawl_books should emit metadata: job_id."""

    def test_emits_job_id_metadata(self) -> None:
        """crawl_books should include job_id in materialization metadata."""
        from litmatch.defs.assets.crawl import crawl_books
        from litmatch.defs.resources.scrapyd import ScrapydResource

        scrapyd = ScrapydResource(poll_interval_seconds=0, timeout_seconds=10)

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "ok", "jobid": "meta-job-123"}
            mock_httpx.post.return_value = mock_response

            list_response = MagicMock()
            list_response.status_code = 200
            list_response.json.return_value = {
                "status": "ok",
                "pending": [],
                "running": [],
                "finished": [{"id": "meta-job-123", "spider": "bookmarks"}],
            }
            mock_httpx.get.return_value = list_response

            result = dg.materialize_to_memory(
                [crawl_books],
                resources={"scrapyd": scrapyd},
            )

        assert result.success
        metadata = _get_metadata(result, "crawl_books")
        assert "job_id" in metadata
        assert metadata["job_id"] == "meta-job-123"

    def test_still_produces_output(self) -> None:
        """crawl_books should still produce a usable output value."""
        from litmatch.defs.assets.crawl import crawl_books
        from litmatch.defs.resources.scrapyd import ScrapydResource

        scrapyd = ScrapydResource(poll_interval_seconds=0, timeout_seconds=10)

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"status": "ok", "jobid": "out-job-456"}
            mock_httpx.post.return_value = mock_response

            list_response = MagicMock()
            list_response.status_code = 200
            list_response.json.return_value = {
                "status": "ok",
                "pending": [],
                "running": [],
                "finished": [{"id": "out-job-456", "spider": "bookmarks"}],
            }
            mock_httpx.get.return_value = list_response

            result = dg.materialize_to_memory(
                [crawl_books],
                resources={"scrapyd": scrapyd},
            )

        assert result.success
        output = result.output_for_node("crawl_books")
        assert output == "out-job-456"


# -- Helpers ------------------------------------------------------------------


def _get_metadata(result: dg.ExecuteInProcessResult, asset_name: str) -> dict:
    """Extract metadata from a materialization event as a plain dict.

    Unwraps MetadataValue wrappers to get the underlying Python values.
    """
    for event in result.all_events:
        if (
            event.event_type_value == "ASSET_MATERIALIZATION"
            and event.event_specific_data is not None
        ):
            materialization = event.event_specific_data.materialization
            if materialization.asset_key.path[-1] == asset_name:
                result_dict: dict = {}
                for key, value in materialization.metadata.items():
                    if isinstance(value, dg.IntMetadataValue):
                        result_dict[key] = value.value
                    elif isinstance(value, dg.FloatMetadataValue):
                        result_dict[key] = value.value
                    elif isinstance(value, dg.TextMetadataValue):
                        result_dict[key] = value.value
                    else:
                        result_dict[key] = value
                return result_dict
    raise AssertionError(
        f"No ASSET_MATERIALIZATION event found for asset '{asset_name}'"
    )


def _unwrap_metadata(metadata: dict) -> dict:
    """Unwrap MetadataValue wrappers from Output.metadata to plain Python values.

    When accessing Output.metadata directly (not through materialization events),
    values are MetadataValue instances (IntMetadataValue, FloatMetadataValue, etc.).
    """
    result: dict = {}
    for key, value in metadata.items():
        if hasattr(value, "value"):
            result[key] = value.value
        else:
            result[key] = value
    return result


def _find_output(outputs: list, output_name: str) -> dg.Output | None:
    """Find an Output with the given name from a list of yielded outputs."""
    for output in outputs:
        if isinstance(output, dg.Output) and output.output_name == output_name:
            return output
    return None
