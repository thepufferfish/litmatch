"""Tests for staging_data_sensor with incremental processing.

Tests the sensor's ability to detect new rows during a long-running
crawl (same crawl_job_id) by tracking both job_id and max_id in the cursor.
"""
from unittest.mock import MagicMock, patch

import dagster as dg

from litmatch.defs.resources.database import DatabaseResource
from litmatch.defs.sensors.data_freshness import staging_data_sensor
from litmatch.defs.utils.staging import StagingDataState


def _make_mock_engine() -> MagicMock:
    """Build a mock SQLAlchemy engine."""
    mock_engine = MagicMock()
    mock_engine.dispose = MagicMock()
    return mock_engine


class TestSensorCursorFormat:
    """Tests for cursor format: {job_id}:{max_id}."""

    @patch("litmatch.defs.sensors.data_freshness.get_staging_data_state")
    def test_triggers_on_first_run_with_no_cursor(self, mock_get_state):
        """Should trigger when cursor is None and data exists."""
        mock_get_state.return_value = StagingDataState(
            crawl_job_id="first-crawl-123",
            max_id=10,
            row_count=5,
        )

        db_resource = DatabaseResource(connection_string="postgresql://test:test@localhost/test")
        mock_engine = _make_mock_engine()

        with patch.object(DatabaseResource, "get_engine", return_value=mock_engine):
            context = dg.build_sensor_context(cursor=None, resources={"database": db_resource})
            result = staging_data_sensor.evaluate_tick(context)

        assert len(result.run_requests) == 1
        assert result.cursor == "first-crawl-123:10"

    @patch("litmatch.defs.sensors.data_freshness.get_staging_data_state")
    def test_skips_when_no_new_data(self, mock_get_state):
        """Should skip when cursor matches current state."""
        mock_get_state.return_value = StagingDataState(
            crawl_job_id="existing-job-456",
            max_id=42,
            row_count=10,
        )

        db_resource = DatabaseResource(connection_string="postgresql://test:test@localhost/test")
        mock_engine = _make_mock_engine()

        with patch.object(DatabaseResource, "get_engine", return_value=mock_engine):
            context = dg.build_sensor_context(
                cursor="existing-job-456:42",
                resources={"database": db_resource}
            )
            result = staging_data_sensor.evaluate_tick(context)

        assert len(result.run_requests) == 0
        assert result.cursor == "existing-job-456:42"

    @patch("litmatch.defs.sensors.data_freshness.get_staging_data_state")
    def test_triggers_when_new_rows_added_to_same_job(self, mock_get_state):
        """Should trigger when new rows appear for the same crawl_job_id."""
        mock_get_state.return_value = StagingDataState(
            crawl_job_id="long-running-crawl-789",
            max_id=50,
            row_count=15,
        )

        db_resource = DatabaseResource(connection_string="postgresql://test:test@localhost/test")
        mock_engine = _make_mock_engine()

        with patch.object(DatabaseResource, "get_engine", return_value=mock_engine):
            context = dg.build_sensor_context(
                cursor="long-running-crawl-789:30",
                resources={"database": db_resource}
            )
            result = staging_data_sensor.evaluate_tick(context)

        assert len(result.run_requests) == 1
        assert result.cursor == "long-running-crawl-789:50"

    @patch("litmatch.defs.sensors.data_freshness.get_staging_data_state")
    def test_triggers_when_new_crawl_job_starts(self, mock_get_state):
        """Should trigger when a new crawl_job_id appears."""
        mock_get_state.return_value = StagingDataState(
            crawl_job_id="new-job-222",
            max_id=5,
            row_count=5,
        )

        db_resource = DatabaseResource(connection_string="postgresql://test:test@localhost/test")
        mock_engine = _make_mock_engine()

        with patch.object(DatabaseResource, "get_engine", return_value=mock_engine):
            context = dg.build_sensor_context(
                cursor="old-job-111:100",
                resources={"database": db_resource}
            )
            result = staging_data_sensor.evaluate_tick(context)

        assert len(result.run_requests) == 1
        assert result.cursor == "new-job-222:5"


class TestSensorBackwardCompatibility:
    """Tests for backward compatibility with old cursor format (just job_id)."""

    @patch("litmatch.defs.sensors.data_freshness.get_staging_data_state")
    def test_handles_legacy_cursor_format(self, mock_get_state):
        """Should handle old cursor format: just 'job_id' without ':max_id'."""
        mock_get_state.return_value = StagingDataState(
            crawl_job_id="legacy-job-999",
            max_id=100,
            row_count=50,
        )

        db_resource = DatabaseResource(connection_string="postgresql://test:test@localhost/test")
        mock_engine = _make_mock_engine()

        with patch.object(DatabaseResource, "get_engine", return_value=mock_engine):
            # Old cursor format: just the job_id
            context = dg.build_sensor_context(
                cursor="legacy-job-999",
                resources={"database": db_resource}
            )
            result = staging_data_sensor.evaluate_tick(context)

        # Should upgrade to new format
        assert result.cursor is not None
        assert ":" in result.cursor

    @patch("litmatch.defs.sensors.data_freshness.get_staging_data_state")
    def test_upgrades_legacy_cursor_when_new_data_arrives(self, mock_get_state):
        """Should upgrade legacy cursor to new format when new data arrives."""
        mock_get_state.return_value = StagingDataState(
            crawl_job_id="upgrade-job-555",
            max_id=75,
            row_count=20,
        )

        db_resource = DatabaseResource(connection_string="postgresql://test:test@localhost/test")
        mock_engine = _make_mock_engine()

        with patch.object(DatabaseResource, "get_engine", return_value=mock_engine):
            # Legacy cursor (just job_id, treated as max_id=0)
            context = dg.build_sensor_context(
                cursor="upgrade-job-555",
                resources={"database": db_resource}
            )
            result = staging_data_sensor.evaluate_tick(context)

        # Should trigger and use new cursor format
        assert len(result.run_requests) == 1
        assert result.cursor == "upgrade-job-555:75"


class TestSensorEdgeCases:
    """Tests for edge cases and error conditions."""

    @patch("litmatch.defs.sensors.data_freshness.get_staging_data_state")
    def test_skips_when_table_empty(self, mock_get_state):
        """Should skip gracefully when staging table is empty."""
        mock_get_state.return_value = None

        db_resource = DatabaseResource(connection_string="postgresql://test:test@localhost/test")
        mock_engine = _make_mock_engine()

        with patch.object(DatabaseResource, "get_engine", return_value=mock_engine):
            context = dg.build_sensor_context(cursor=None, resources={"database": db_resource})
            result = staging_data_sensor.evaluate_tick(context)

        assert len(result.run_requests) == 0
        assert result.cursor is None

    @patch("litmatch.defs.sensors.data_freshness.get_staging_data_state")
    def test_handles_multiple_incremental_updates(self, mock_get_state):
        """Should handle multiple incremental updates during long crawl."""
        job_id = "multi-day-crawl-777"
        db_resource = DatabaseResource(connection_string="postgresql://test:test@localhost/test")
        mock_engine = _make_mock_engine()

        with patch.object(DatabaseResource, "get_engine", return_value=mock_engine):
            # Day 1: Initial data
            mock_get_state.return_value = StagingDataState(job_id, 10, 10)
            context1 = dg.build_sensor_context(cursor=None, resources={"database": db_resource})
            result1 = staging_data_sensor.evaluate_tick(context1)
            assert len(result1.run_requests) == 1
            assert result1.cursor == f"{job_id}:10"

            # Day 2: More data arrives
            mock_get_state.return_value = StagingDataState(job_id, 25, 25)
            context2 = dg.build_sensor_context(cursor=result1.cursor, resources={"database": db_resource})
            result2 = staging_data_sensor.evaluate_tick(context2)
            assert len(result2.run_requests) == 1
            assert result2.cursor == f"{job_id}:25"

            # Day 3: Even more data
            mock_get_state.return_value = StagingDataState(job_id, 40, 40)
            context3 = dg.build_sensor_context(cursor=result2.cursor, resources={"database": db_resource})
            result3 = staging_data_sensor.evaluate_tick(context3)
            assert len(result3.run_requests) == 1
            assert result3.cursor == f"{job_id}:40"

            # Day 4: No new data
            mock_get_state.return_value = StagingDataState(job_id, 40, 40)
            context4 = dg.build_sensor_context(cursor=result3.cursor, resources={"database": db_resource})
            result4 = staging_data_sensor.evaluate_tick(context4)
            assert len(result4.run_requests) == 0
            assert result4.cursor == f"{job_id}:40"
