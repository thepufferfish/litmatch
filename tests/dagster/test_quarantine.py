"""Tests for Phase 3: Quarantine persistence for validation errors.

validate_raw_books should write validation errors to timestamped JSONL files
in a quarantine directory for later analysis and reprocessing.

TDD Phase: RED -- these tests should fail before implementation.
"""
import json
import os
import tempfile

import dagster as dg
import pytest


class TestQuarantineFilePersistence:
    """validate_raw_books should write quarantine records to JSONL files."""

    def test_writes_quarantine_file_when_errors_exist(self) -> None:
        """When validation errors occur, a quarantine JSONL file should be created."""
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

        with tempfile.TemporaryDirectory() as tmp_dir:
            path_resource = PathResource(raw_data_dir=tmp_dir)
            context = dg.build_asset_context(resources={"path": path_resource})
            outputs = list(validate_raw_books(context, [bad_record]))

            # Check that a quarantine file was created
            quarantine_dir = os.path.join(tmp_dir, "quarantine")
            assert os.path.isdir(quarantine_dir), (
                "Quarantine directory should be created"
            )

            quarantine_files = os.listdir(quarantine_dir)
            assert len(quarantine_files) == 1
            assert quarantine_files[0].endswith(".jsonl")

    def test_quarantine_file_has_timestamped_name(self) -> None:
        """The quarantine file should be named with a timestamp."""
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

        with tempfile.TemporaryDirectory() as tmp_dir:
            path_resource = PathResource(raw_data_dir=tmp_dir)
            context = dg.build_asset_context(resources={"path": path_resource})
            list(validate_raw_books(context, [bad_record]))

            quarantine_dir = os.path.join(tmp_dir, "quarantine")
            quarantine_files = os.listdir(quarantine_dir)
            filename = quarantine_files[0]

            # Should match pattern: quarantine_YYYYMMDD_HHMMSS_ffffff.jsonl
            assert filename.startswith("quarantine_")
            assert filename.endswith(".jsonl")
            # Extract timestamp part
            timestamp_part = filename[len("quarantine_"):-len(".jsonl")]
            # Format is YYYYMMDD_HHMMSS_ffffff (8+1+6+1+6 = 22 chars)
            assert len(timestamp_part) == 22

    def test_quarantine_file_contains_error_records(self) -> None:
        """Each line in the quarantine file should be a JSON error record."""
        from litmatch.defs.assets.validate import validate_raw_books
        from litmatch.defs.resources.path import PathResource

        bad_record = {
            "title": "",
            "author": "Some Author",
            "publisher": "",
            "publish_date": "",
            "description": "",
            "genres": [],
            "url": "",
            "cover": None,
            "last_scraped": "",
            "reviews": [],
        }

        with tempfile.TemporaryDirectory() as tmp_dir:
            path_resource = PathResource(raw_data_dir=tmp_dir)
            context = dg.build_asset_context(resources={"path": path_resource})
            list(validate_raw_books(context, [bad_record]))

            quarantine_dir = os.path.join(tmp_dir, "quarantine")
            quarantine_files = os.listdir(quarantine_dir)
            filepath = os.path.join(quarantine_dir, quarantine_files[0])

            with open(filepath, "r") as f:
                lines = f.readlines()

            assert len(lines) == 1
            record = json.loads(lines[0])
            assert "url" in record
            assert "title" in record
            assert "errors" in record
            assert isinstance(record["errors"], list)
            assert len(record["errors"]) > 0

    def test_no_quarantine_file_when_all_valid(
        self, sample_records: list[dict]
    ) -> None:
        """When all records are valid, no quarantine file should be created."""
        from litmatch.defs.assets.validate import validate_raw_books
        from litmatch.defs.resources.path import PathResource

        with tempfile.TemporaryDirectory() as tmp_dir:
            path_resource = PathResource(raw_data_dir=tmp_dir)
            context = dg.build_asset_context(resources={"path": path_resource})
            list(validate_raw_books(context, sample_records))

            quarantine_dir = os.path.join(tmp_dir, "quarantine")
            if os.path.exists(quarantine_dir):
                assert len(os.listdir(quarantine_dir)) == 0

    def test_multiple_errors_written_to_same_file(self) -> None:
        """Multiple validation errors should all be written to the same file."""
        from litmatch.defs.assets.validate import validate_raw_books
        from litmatch.defs.resources.path import PathResource

        bad_records = [
            {
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
            },
            {
                "title": "",
                "author": "",
                "publisher": "",
                "publish_date": "",
                "description": "",
                "genres": [],
                "url": "https://example.com",
                "cover": None,
                "last_scraped": "",
                "reviews": [],
            },
        ]

        with tempfile.TemporaryDirectory() as tmp_dir:
            path_resource = PathResource(raw_data_dir=tmp_dir)
            context = dg.build_asset_context(resources={"path": path_resource})
            list(validate_raw_books(context, bad_records))

            quarantine_dir = os.path.join(tmp_dir, "quarantine")
            quarantine_files = os.listdir(quarantine_dir)
            assert len(quarantine_files) == 1

            filepath = os.path.join(quarantine_dir, quarantine_files[0])
            with open(filepath, "r") as f:
                lines = f.readlines()

            assert len(lines) == 2

    def test_quarantine_metadata_includes_file_path(self) -> None:
        """validation_errors Output should include quarantine_file path in metadata."""
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

        with tempfile.TemporaryDirectory() as tmp_dir:
            path_resource = PathResource(raw_data_dir=tmp_dir)
            context = dg.build_asset_context(resources={"path": path_resource})
            outputs = list(validate_raw_books(context, [bad_record]))

            errors_output = _find_output(outputs, "validation_errors")
            assert errors_output is not None
            assert "quarantine_file" in errors_output.metadata


class TestPathResourceQuarantineDir:
    """PathResource should provide a quarantine directory path."""

    def test_has_quarantine_dir_property(self) -> None:
        """PathResource should have a quarantine_dir property."""
        from litmatch.defs.resources.path import PathResource

        path = PathResource(raw_data_dir="/tmp/test")
        assert hasattr(path, "quarantine_dir")
        assert path.quarantine_dir == "/tmp/test/quarantine"


# -- Helpers ------------------------------------------------------------------


def _find_output(outputs: list, output_name: str) -> dg.Output | None:
    """Find an Output with the given name from a list of yielded outputs."""
    for output in outputs:
        if isinstance(output, dg.Output) and output.output_name == output_name:
            return output
    return None
