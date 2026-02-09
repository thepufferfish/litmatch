"""Unit tests for the startup ETL sensor.

The startup_etl_sensor fires exactly once on first evaluation if books.jsonl
exists, seeding the database on initial deployment. Uses a cursor to track
"already seeded" state, preventing re-runs on daemon restarts.
"""
import json
import os
from unittest.mock import patch

import dagster as dg
import pytest

from litmatch.defs.sensors.startup_etl import startup_etl_sensor


class TestStartupSensorDefinition:
    """Tests that the sensor is properly defined as a Dagster sensor."""

    def test_sensor_is_a_sensor_definition(self) -> None:
        """The decorated function should produce a SensorDefinition."""
        assert isinstance(startup_etl_sensor, dg.SensorDefinition)

    def test_sensor_targets_etl_job(self) -> None:
        """The sensor must target the etl_pipeline job."""
        targets = startup_etl_sensor.targets
        assert len(targets) > 0
        job_names = [t.job_name for t in targets if hasattr(t, "job_name")]
        assert "etl_pipeline" in job_names

    def test_sensor_has_descriptive_name(self) -> None:
        """The sensor should have a meaningful, distinct name."""
        assert startup_etl_sensor.name == "startup_etl_sensor"


class TestStartupSensorLogic:
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

    def test_first_run_with_data_triggers_pipeline(self, data_dir: str) -> None:
        """On first evaluation with books.jsonl present, trigger the ETL pipeline."""
        from litmatch.defs.resources.path import PathResource

        context = dg.build_sensor_context(
            resources={"path": PathResource(raw_data_dir=data_dir)},
        )
        result = startup_etl_sensor.evaluate_tick(context)

        assert len(result.run_requests) == 1
        assert result.cursor == "seeded"

    def test_second_run_does_not_trigger(self, data_dir: str) -> None:
        """After the cursor is set to 'seeded', no further runs should trigger."""
        from litmatch.defs.resources.path import PathResource

        # First tick: triggers
        context = dg.build_sensor_context(
            resources={"path": PathResource(raw_data_dir=data_dir)},
        )
        first_result = startup_etl_sensor.evaluate_tick(context)
        assert len(first_result.run_requests) == 1

        # Second tick: cursor is 'seeded', should not trigger
        context = dg.build_sensor_context(
            cursor="seeded",
            resources={"path": PathResource(raw_data_dir=data_dir)},
        )
        second_result = startup_etl_sensor.evaluate_tick(context)

        assert len(second_result.run_requests) == 0
        assert second_result.cursor == "seeded"

    def test_missing_file_does_not_trigger(self, empty_data_dir: str) -> None:
        """If books.jsonl does not exist, skip without error and do not set cursor."""
        from litmatch.defs.resources.path import PathResource

        context = dg.build_sensor_context(
            resources={"path": PathResource(raw_data_dir=empty_data_dir)},
        )
        result = startup_etl_sensor.evaluate_tick(context)

        assert len(result.run_requests) == 0
        # Cursor should NOT be set to 'seeded' so it retries on next tick
        assert result.cursor != "seeded"

    def test_file_appears_after_initial_miss(self, tmp_path) -> None:
        """If the file was missing on first tick but appears later, trigger on next tick."""
        from litmatch.defs.resources.path import PathResource

        data_dir = str(tmp_path)

        # First tick: no file, no trigger
        context = dg.build_sensor_context(
            resources={"path": PathResource(raw_data_dir=data_dir)},
        )
        first_result = startup_etl_sensor.evaluate_tick(context)
        assert len(first_result.run_requests) == 0

        # File appears
        jsonl_path = tmp_path / "books.jsonl"
        sample = {"title": "Test Book", "author": "Author"}
        jsonl_path.write_text(json.dumps(sample) + "\n")

        # Second tick: file exists, cursor not 'seeded', should trigger
        context = dg.build_sensor_context(
            cursor=first_result.cursor,
            resources={"path": PathResource(raw_data_dir=data_dir)},
        )
        second_result = startup_etl_sensor.evaluate_tick(context)

        assert len(second_result.run_requests) == 1
        assert second_result.cursor == "seeded"

    def test_run_key_is_deterministic(self, data_dir: str) -> None:
        """The run_key should be fixed ('startup_seed') for deduplication."""
        from litmatch.defs.resources.path import PathResource

        context = dg.build_sensor_context(
            resources={"path": PathResource(raw_data_dir=data_dir)},
        )
        result = startup_etl_sensor.evaluate_tick(context)

        assert len(result.run_requests) == 1
        assert result.run_requests[0].run_key == "startup_seed"


class TestStartupSensorRegistration:
    """Tests that the sensor is registered in the Dagster Definitions."""

    def test_sensor_registered_in_definitions(self) -> None:
        """The startup_etl_sensor should be present in the Dagster Definitions."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
            "RAW_DATA_DIR": "/tmp/test",
        }):
            from litmatch.definitions import defs

            resolved = defs.load_fn()
            sensor_names = [s.name for s in resolved.sensors]
            assert "startup_etl_sensor" in sensor_names
