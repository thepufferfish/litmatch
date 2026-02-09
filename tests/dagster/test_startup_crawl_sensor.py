"""Unit tests for the startup_crawl_sensor.

The startup_crawl_sensor is a state machine that fires exactly once on
first deployment to trigger a crawl-and-load pipeline. It checks Scrapyd
health before scheduling and uses cursor states to track progress.

State machine:
  None (no cursor) -> "crawl_requested" -> "completed"

If Scrapyd is unhealthy on first tick, the sensor retries (cursor stays None).
Once the crawl job is requested, cursor becomes "crawl_requested".
The sensor is done once it transitions to "completed".
"""
import json
import os
from unittest.mock import MagicMock, patch

import dagster as dg
import pytest

from litmatch.defs.resources.scrapyd import ScrapydResource


class TestStartupCrawlSensorDefinition:
    """Tests that the sensor is properly defined as a Dagster sensor."""

    def test_sensor_is_a_sensor_definition(self) -> None:
        """The decorated function should produce a SensorDefinition."""
        from litmatch.defs.sensors.startup_crawl import startup_crawl_sensor

        assert isinstance(startup_crawl_sensor, dg.SensorDefinition)

    def test_sensor_has_descriptive_name(self) -> None:
        """The sensor should have a meaningful, distinct name."""
        from litmatch.defs.sensors.startup_crawl import startup_crawl_sensor

        assert startup_crawl_sensor.name == "startup_crawl_sensor"

    def test_sensor_targets_crawl_and_load_job(self) -> None:
        """The sensor must target the crawl_and_load job."""
        from litmatch.defs.sensors.startup_crawl import startup_crawl_sensor

        targets = startup_crawl_sensor.targets
        assert len(targets) > 0
        job_names = [t.job_name for t in targets if hasattr(t, "job_name")]
        assert "crawl_and_load" in job_names

    def test_sensor_has_minimum_interval(self) -> None:
        """The sensor should poll at a reasonable interval."""
        from litmatch.defs.sensors.startup_crawl import startup_crawl_sensor

        assert startup_crawl_sensor.minimum_interval_seconds >= 30


class TestStartupCrawlSensorFirstTick:
    """Tests for the first tick when no cursor exists."""

    def test_healthy_scrapyd_triggers_crawl(self) -> None:
        """On first tick with healthy Scrapyd, should request a crawl_and_load run."""
        from litmatch.defs.sensors.startup_crawl import startup_crawl_sensor

        scrapyd = ScrapydResource()

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            # is_healthy returns True
            health_response = MagicMock()
            health_response.status_code = 200
            mock_httpx.get.return_value = health_response

            context = dg.build_sensor_context(
                resources={"scrapyd": scrapyd},
            )
            result = startup_crawl_sensor.evaluate_tick(context)

        assert len(result.run_requests) == 1
        assert result.cursor == "crawl_requested"

    def test_unhealthy_scrapyd_retries(self) -> None:
        """On first tick with unhealthy Scrapyd, should skip and retry."""
        from litmatch.defs.sensors.startup_crawl import startup_crawl_sensor

        scrapyd = ScrapydResource()

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.get.side_effect = ConnectionError("refused")

            context = dg.build_sensor_context(
                resources={"scrapyd": scrapyd},
            )
            result = startup_crawl_sensor.evaluate_tick(context)

        assert len(result.run_requests) == 0
        # Cursor should remain None so it retries
        assert result.cursor is None

    def test_run_request_has_deterministic_key(self) -> None:
        """The run_key should be fixed for deduplication."""
        from litmatch.defs.sensors.startup_crawl import startup_crawl_sensor

        scrapyd = ScrapydResource()

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            health_response = MagicMock()
            health_response.status_code = 200
            mock_httpx.get.return_value = health_response

            context = dg.build_sensor_context(
                resources={"scrapyd": scrapyd},
            )
            result = startup_crawl_sensor.evaluate_tick(context)

        assert result.run_requests[0].run_key == "startup_crawl"


class TestStartupCrawlSensorCrawlRequested:
    """Tests for when cursor is 'crawl_requested' (crawl already triggered)."""

    def test_crawl_requested_does_not_retrigger(self) -> None:
        """Once cursor is 'crawl_requested', no more runs should be requested."""
        from litmatch.defs.sensors.startup_crawl import startup_crawl_sensor

        scrapyd = ScrapydResource()

        context = dg.build_sensor_context(
            cursor="crawl_requested",
            resources={"scrapyd": scrapyd},
        )
        result = startup_crawl_sensor.evaluate_tick(context)

        assert len(result.run_requests) == 0
        assert result.cursor == "completed"


class TestStartupCrawlSensorCompleted:
    """Tests for when cursor is 'completed' (permanently done)."""

    def test_completed_stays_completed(self) -> None:
        """Once cursor is 'completed', sensor should do nothing forever."""
        from litmatch.defs.sensors.startup_crawl import startup_crawl_sensor

        scrapyd = ScrapydResource()

        context = dg.build_sensor_context(
            cursor="completed",
            resources={"scrapyd": scrapyd},
        )
        result = startup_crawl_sensor.evaluate_tick(context)

        assert len(result.run_requests) == 0
        assert result.cursor == "completed"


class TestStartupCrawlSensorFullLifecycle:
    """Tests for the full sensor lifecycle across multiple ticks."""

    def test_full_lifecycle_healthy_scrapyd(self) -> None:
        """Full lifecycle: None -> crawl_requested -> completed."""
        from litmatch.defs.sensors.startup_crawl import startup_crawl_sensor

        scrapyd = ScrapydResource()

        # Tick 1: First tick, Scrapyd healthy -> triggers crawl
        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            health_response = MagicMock()
            health_response.status_code = 200
            mock_httpx.get.return_value = health_response

            context = dg.build_sensor_context(
                resources={"scrapyd": scrapyd},
            )
            result1 = startup_crawl_sensor.evaluate_tick(context)

        assert len(result1.run_requests) == 1
        assert result1.cursor == "crawl_requested"

        # Tick 2: Cursor is 'crawl_requested' -> transitions to 'completed'
        context = dg.build_sensor_context(
            cursor=result1.cursor,
            resources={"scrapyd": scrapyd},
        )
        result2 = startup_crawl_sensor.evaluate_tick(context)

        assert len(result2.run_requests) == 0
        assert result2.cursor == "completed"

        # Tick 3: Cursor is 'completed' -> stays completed
        context = dg.build_sensor_context(
            cursor=result2.cursor,
            resources={"scrapyd": scrapyd},
        )
        result3 = startup_crawl_sensor.evaluate_tick(context)

        assert len(result3.run_requests) == 0
        assert result3.cursor == "completed"

    def test_lifecycle_with_unhealthy_then_healthy(self) -> None:
        """If Scrapyd is initially unhealthy, retries until healthy."""
        from litmatch.defs.sensors.startup_crawl import startup_crawl_sensor

        scrapyd = ScrapydResource()

        # Tick 1: Scrapyd unhealthy -> no trigger, cursor stays None
        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.get.side_effect = ConnectionError("refused")

            context = dg.build_sensor_context(
                resources={"scrapyd": scrapyd},
            )
            result1 = startup_crawl_sensor.evaluate_tick(context)

        assert len(result1.run_requests) == 0
        assert result1.cursor is None

        # Tick 2: Scrapyd becomes healthy -> triggers crawl
        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            health_response = MagicMock()
            health_response.status_code = 200
            mock_httpx.get.return_value = health_response

            context = dg.build_sensor_context(
                cursor=result1.cursor,
                resources={"scrapyd": scrapyd},
            )
            result2 = startup_crawl_sensor.evaluate_tick(context)

        assert len(result2.run_requests) == 1
        assert result2.cursor == "crawl_requested"


class TestStartupCrawlSensorConstants:
    """Tests for sensor cursor state constants."""

    def test_cursor_states_are_strings(self) -> None:
        """Cursor state constants should be non-empty strings."""
        from litmatch.defs.sensors.startup_crawl import (
            CURSOR_CRAWL_REQUESTED,
            CURSOR_COMPLETED,
        )

        assert isinstance(CURSOR_CRAWL_REQUESTED, str)
        assert len(CURSOR_CRAWL_REQUESTED) > 0
        assert isinstance(CURSOR_COMPLETED, str)
        assert len(CURSOR_COMPLETED) > 0

    def test_cursor_states_are_distinct(self) -> None:
        """Each cursor state should be unique."""
        from litmatch.defs.sensors.startup_crawl import (
            CURSOR_CRAWL_REQUESTED,
            CURSOR_COMPLETED,
        )

        assert CURSOR_CRAWL_REQUESTED != CURSOR_COMPLETED
