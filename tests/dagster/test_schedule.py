"""Tests for Phase 4: Weekly ETL schedule.

A cron-based schedule should trigger the etl_pipeline job every
Sunday at midnight UTC.

TDD Phase: RED -- these tests should fail before implementation.
"""
import os
from unittest.mock import patch

import dagster as dg
import pytest


class TestWeeklyEtlScheduleDefinition:
    """The weekly_etl_schedule should be properly defined as a Dagster schedule."""

    def test_schedule_is_importable(self) -> None:
        """weekly_etl_schedule should be importable from the schedules module."""
        from litmatch.defs.schedules import weekly_etl_schedule

        assert weekly_etl_schedule is not None

    def test_schedule_is_a_schedule_definition(self) -> None:
        """The schedule should be a Dagster ScheduleDefinition."""
        from litmatch.defs.schedules import weekly_etl_schedule

        assert isinstance(weekly_etl_schedule, dg.ScheduleDefinition)

    def test_schedule_name(self) -> None:
        """The schedule should be named 'weekly_etl_schedule'."""
        from litmatch.defs.schedules import weekly_etl_schedule

        assert weekly_etl_schedule.name == "weekly_etl_schedule"

    def test_schedule_targets_etl_pipeline(self) -> None:
        """The schedule should target the etl_pipeline job."""
        from litmatch.defs.schedules import weekly_etl_schedule

        assert weekly_etl_schedule.job_name == "etl_pipeline"

    def test_schedule_cron_is_sunday_midnight_utc(self) -> None:
        """The schedule should run at midnight UTC every Sunday (0 0 * * 0)."""
        from litmatch.defs.schedules import weekly_etl_schedule

        assert weekly_etl_schedule.cron_schedule == "0 0 * * 0"

    def test_schedule_has_description(self) -> None:
        """The schedule should have a meaningful description."""
        from litmatch.defs.schedules import weekly_etl_schedule

        assert weekly_etl_schedule.description is not None
        assert len(weekly_etl_schedule.description) > 0

    def test_schedule_default_status_is_stopped(self) -> None:
        """The schedule should default to STOPPED (opt-in activation)."""
        from litmatch.defs.schedules import weekly_etl_schedule

        assert weekly_etl_schedule.default_status == dg.DefaultScheduleStatus.STOPPED

    def test_schedule_execution_timezone_is_utc(self) -> None:
        """The schedule should execute in UTC timezone."""
        from litmatch.defs.schedules import weekly_etl_schedule

        assert weekly_etl_schedule.execution_timezone == "UTC"


class TestScheduleRegistration:
    """The schedule should be registered in the Dagster Definitions."""

    def test_schedule_in_definitions(self) -> None:
        """The weekly_etl_schedule should be registered in the Dagster Definitions."""
        with patch.dict(os.environ, {
            "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
            "RAW_DATA_DIR": "/tmp/test",
        }):
            from litmatch.definitions import defs

            resolved = defs.load_fn()
            schedule_names = [s.name for s in resolved.schedules]
            assert "weekly_etl_schedule" in schedule_names
