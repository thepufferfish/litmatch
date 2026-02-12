"""Unit tests for the staging data sensor.

The staging_data_sensor watches the raw_books_staging table for new crawl data
and triggers the ETL pipeline job when a new crawl_job_id appears.
"""
from unittest.mock import MagicMock, patch

import dagster as dg
import pytest

from litmatch.defs.resources.database import DatabaseResource
from litmatch.defs.sensors.data_freshness import staging_data_sensor


class TestStagingDataSensorDefinition:
    """Tests that the sensor is properly defined as a Dagster sensor."""

    def test_sensor_is_a_sensor_definition(self) -> None:
        assert isinstance(staging_data_sensor, dg.SensorDefinition)

    def test_sensor_targets_etl_job(self) -> None:
        targets = staging_data_sensor.targets
        assert len(targets) > 0
        job_names = [t.job_name for t in targets if hasattr(t, "job_name")]
        assert "etl_pipeline" in job_names

    def test_sensor_has_descriptive_name(self) -> None:
        assert staging_data_sensor.name == "staging_data_sensor"

    def test_sensor_has_minimum_interval(self) -> None:
        assert staging_data_sensor.minimum_interval_seconds >= 60


def _make_mock_engine(job_id: str | None) -> MagicMock:
    """Build a mock SQLAlchemy engine that returns a staged crawl_job_id.

    Args:
        job_id: The crawl_job_id to return from the query, or None
                to simulate an empty staging table.
    """
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_result = MagicMock()
    mock_result.first.return_value = (job_id,) if job_id is not None else None
    mock_conn.execute.return_value = mock_result
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    mock_engine.connect.return_value = mock_conn
    mock_engine.dispose = MagicMock()
    return mock_engine


class TestStagingDataSensorLogic:
    """Tests for the sensor evaluation logic."""

    @patch("litmatch.defs.sensors.data_freshness.get_latest_crawl_job_id")
    def test_first_run_with_data_triggers_pipeline(self, mock_get_latest) -> None:
        mock_get_latest.return_value = "job-abc-123"
        db_resource = DatabaseResource(connection_string="postgresql://test:test@localhost/test")
        mock_engine = _make_mock_engine("job-abc-123")

        with patch.object(DatabaseResource, "get_engine", return_value=mock_engine):
            context = dg.build_sensor_context(resources={"database": db_resource})
            result = staging_data_sensor.evaluate_tick(context)

        assert len(result.run_requests) == 1
        assert result.run_requests[0].run_key == "job-abc-123"
        assert result.cursor == "job-abc-123"

    @patch("litmatch.defs.sensors.data_freshness.get_latest_crawl_job_id")
    def test_unchanged_data_does_not_trigger(self, mock_get_latest) -> None:
        mock_get_latest.return_value = "job-abc-123"
        db_resource = DatabaseResource(connection_string="postgresql://test:test@localhost/test")
        mock_engine = _make_mock_engine("job-abc-123")

        with patch.object(DatabaseResource, "get_engine", return_value=mock_engine):
            context = dg.build_sensor_context(
                cursor="job-abc-123",
                resources={"database": db_resource},
            )
            result = staging_data_sensor.evaluate_tick(context)

        assert len(result.run_requests) == 0
        assert result.cursor == "job-abc-123"

    @patch("litmatch.defs.sensors.data_freshness.get_latest_crawl_job_id")
    def test_new_crawl_triggers_pipeline(self, mock_get_latest) -> None:
        mock_get_latest.return_value = "job-new-456"
        db_resource = DatabaseResource(connection_string="postgresql://test:test@localhost/test")
        mock_engine = _make_mock_engine("job-new-456")

        with patch.object(DatabaseResource, "get_engine", return_value=mock_engine):
            context = dg.build_sensor_context(
                cursor="job-old-123",
                resources={"database": db_resource},
            )
            result = staging_data_sensor.evaluate_tick(context)

        assert len(result.run_requests) == 1
        assert result.run_requests[0].run_key == "job-new-456"
        assert result.cursor == "job-new-456"

    @patch("litmatch.defs.sensors.data_freshness.get_latest_crawl_job_id")
    def test_empty_staging_table_skips(self, mock_get_latest) -> None:
        mock_get_latest.return_value = None
        db_resource = DatabaseResource(connection_string="postgresql://test:test@localhost/test")
        mock_engine = _make_mock_engine(None)

        with patch.object(DatabaseResource, "get_engine", return_value=mock_engine):
            context = dg.build_sensor_context(resources={"database": db_resource})
            result = staging_data_sensor.evaluate_tick(context)

        assert len(result.run_requests) == 0


class TestEtlPipelineJob:
    """Tests for the etl_pipeline job definition."""

    def test_etl_pipeline_is_a_job(self) -> None:
        from litmatch.defs.jobs import etl_pipeline
        assert etl_pipeline is not None
        assert etl_pipeline.name == "etl_pipeline"

    def test_sensor_registered_in_definitions(self) -> None:
        import os
        from unittest.mock import patch

        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
            "RAW_DATA_DIR": "/tmp/test",
        }):
            from litmatch.definitions import defs
            resolved = defs.load_fn()
            sensor_names = [s.name for s in resolved.sensors]
            assert "staging_data_sensor" in sensor_names
