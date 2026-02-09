"""Unit tests for the data freshness sensor.

The data_freshness_sensor watches the books.jsonl file for modifications
and triggers the ETL pipeline job when the file changes.
"""
import os
import time
import json
import tempfile

import dagster as dg
import pytest

from litmatch.defs.sensors.data_freshness import (
    CURSOR_KEY,
    data_freshness_sensor,
)


class TestDataFreshnessSensorDefinition:
    """Tests that the sensor is properly defined as a Dagster sensor."""

    def test_sensor_is_a_sensor_definition(self) -> None:
        """The decorated function should produce a SensorDefinition."""
        assert isinstance(data_freshness_sensor, dg.SensorDefinition)

    def test_sensor_targets_etl_job(self) -> None:
        """The sensor must target the etl_pipeline job."""
        targets = data_freshness_sensor.targets
        assert len(targets) > 0
        job_names = [t.job_name for t in targets if hasattr(t, "job_name")]
        assert "etl_pipeline" in job_names

    def test_sensor_has_descriptive_name(self) -> None:
        """The sensor should have a meaningful name."""
        assert data_freshness_sensor.name == "data_freshness_sensor"

    def test_sensor_has_minimum_interval(self) -> None:
        """The sensor should poll at a reasonable interval (not too frequent)."""
        assert data_freshness_sensor.minimum_interval_seconds >= 30


class TestDataFreshnessSensorLogic:
    """Tests for the sensor evaluation logic using Dagster's build_sensor_context."""

    @pytest.fixture
    def data_dir(self, tmp_path) -> str:
        """Create a temporary data directory with a books.jsonl file."""
        jsonl_path = tmp_path / "books.jsonl"
        sample = {"title": "Test Book", "author": "Author"}
        jsonl_path.write_text(json.dumps(sample) + "\n")
        return str(tmp_path)

    @pytest.fixture
    def empty_data_dir(self, tmp_path) -> str:
        """Create a temporary data directory without a books.jsonl file."""
        return str(tmp_path)

    def test_first_run_triggers_pipeline(self, data_dir: str) -> None:
        """On first evaluation (no cursor), the sensor should trigger a run."""
        from litmatch.defs.resources.path import PathResource

        context = dg.build_sensor_context(
            resources={"path": PathResource(raw_data_dir=data_dir)},
        )
        result = data_freshness_sensor.evaluate_tick(context)

        assert len(result.run_requests) == 1
        assert result.cursor is not None

    def test_unchanged_file_does_not_trigger(self, data_dir: str) -> None:
        """If the file has not changed since last cursor, no run should be requested."""
        from litmatch.defs.resources.path import PathResource

        # First tick: sets the cursor
        context = dg.build_sensor_context(
            resources={"path": PathResource(raw_data_dir=data_dir)},
        )
        first_result = data_freshness_sensor.evaluate_tick(context)
        cursor_after_first = first_result.cursor

        # Second tick: same file, same mtime
        context = dg.build_sensor_context(
            cursor=cursor_after_first,
            resources={"path": PathResource(raw_data_dir=data_dir)},
        )
        second_result = data_freshness_sensor.evaluate_tick(context)

        assert len(second_result.run_requests) == 0

    def test_modified_file_triggers_pipeline(self, data_dir: str) -> None:
        """If the file is modified after the cursor was set, trigger a new run."""
        from litmatch.defs.resources.path import PathResource

        # First tick
        context = dg.build_sensor_context(
            resources={"path": PathResource(raw_data_dir=data_dir)},
        )
        first_result = data_freshness_sensor.evaluate_tick(context)
        cursor_after_first = first_result.cursor

        # Modify the file (ensure mtime changes)
        jsonl_path = os.path.join(data_dir, "books.jsonl")
        time.sleep(0.05)  # Ensure filesystem timestamp granularity
        with open(jsonl_path, "a") as f:
            f.write(json.dumps({"title": "New Book"}) + "\n")

        # Second tick with old cursor
        context = dg.build_sensor_context(
            cursor=cursor_after_first,
            resources={"path": PathResource(raw_data_dir=data_dir)},
        )
        second_result = data_freshness_sensor.evaluate_tick(context)

        assert len(second_result.run_requests) == 1
        assert second_result.cursor != cursor_after_first

    def test_missing_file_skips_without_error(self, empty_data_dir: str) -> None:
        """If the books.jsonl file does not exist, the sensor should skip gracefully."""
        from litmatch.defs.resources.path import PathResource

        context = dg.build_sensor_context(
            resources={"path": PathResource(raw_data_dir=empty_data_dir)},
        )
        result = data_freshness_sensor.evaluate_tick(context)

        assert len(result.run_requests) == 0

    def test_cursor_stores_mtime_as_string(self, data_dir: str) -> None:
        """The cursor should store the file's mtime as a string for serialization."""
        from litmatch.defs.resources.path import PathResource

        context = dg.build_sensor_context(
            resources={"path": PathResource(raw_data_dir=data_dir)},
        )
        result = data_freshness_sensor.evaluate_tick(context)

        # Cursor should be a string representation of a float (mtime)
        cursor = result.cursor
        assert cursor is not None
        float(cursor)  # Should not raise


class TestCursorKey:
    """Tests for the cursor key constant."""

    def test_cursor_key_is_defined(self) -> None:
        """CURSOR_KEY should be a non-empty string constant."""
        assert isinstance(CURSOR_KEY, str)
        assert len(CURSOR_KEY) > 0


class TestEtlPipelineJob:
    """Tests for the etl_pipeline job definition."""

    def test_etl_pipeline_is_a_job(self) -> None:
        """The etl_pipeline should be a Dagster UnresolvedAssetJobDefinition."""
        from litmatch.defs.jobs import etl_pipeline

        assert etl_pipeline is not None
        assert etl_pipeline.name == "etl_pipeline"

    def test_sensor_registered_in_definitions(self) -> None:
        """The sensor and job should be registered in the Dagster Definitions."""
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
            "RAW_DATA_DIR": "/tmp/test",
        }):
            from litmatch.definitions import defs

            # LazyDefinitions must be resolved via load_fn()
            resolved = defs.load_fn()
            sensor_names = [s.name for s in resolved.sensors]
            assert "data_freshness_sensor" in sensor_names
