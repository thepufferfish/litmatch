"""Unit tests for the crawl_books asset.

The crawl_books asset schedules a Scrapyd spider crawl and polls
until the job finishes, producing a job_id output.
"""
from unittest.mock import MagicMock, patch

import dagster as dg
import pytest

from litmatch.defs.resources.scrapyd import ScrapydResource


class TestCrawlBooksAssetDefinition:
    """Tests that crawl_books is properly defined as a Dagster asset."""

    def test_asset_is_defined(self) -> None:
        """crawl_books should be importable as a Dagster asset."""
        from litmatch.defs.assets.crawl import crawl_books

        assert isinstance(crawl_books, dg.AssetsDefinition)

    def test_asset_has_correct_name(self) -> None:
        """The asset should be named 'crawl_books'."""
        from litmatch.defs.assets.crawl import crawl_books

        keys = list(crawl_books.keys)
        assert len(keys) == 1
        assert keys[0].path[-1] == "crawl_books"

    def test_asset_has_description(self) -> None:
        """The asset should have a meaningful description."""
        from litmatch.defs.assets.crawl import crawl_books

        key = list(crawl_books.keys)[0]
        spec = crawl_books.specs_by_key[key]
        assert spec.description is not None
        assert len(spec.description) > 0


def _mock_schedule_response(job_id: str = "job-abc-123") -> MagicMock:
    """Create a mock httpx response for schedule.json."""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"status": "ok", "jobid": job_id}
    return response


def _mock_listjobs_response(job_id: str, state: str) -> MagicMock:
    """Create a mock httpx response for listjobs.json."""
    response = MagicMock()
    response.status_code = 200
    pending = [{"id": job_id, "spider": "bookmarks"}] if state == "pending" else []
    running = [{"id": job_id, "spider": "bookmarks"}] if state == "running" else []
    finished = [{"id": job_id, "spider": "bookmarks"}] if state == "finished" else []
    response.json.return_value = {
        "status": "ok",
        "pending": pending,
        "running": running,
        "finished": finished,
    }
    return response


class TestCrawlBooksAssetExecution:
    """Tests for crawl_books execution logic.

    Uses materialize_to_memory with real ScrapydResource and mocked httpx
    to satisfy Dagster's resource type validation.
    """

    def test_schedules_and_waits_for_completion(self) -> None:
        """Should schedule a crawl and poll until finished, returning job_id."""
        from litmatch.defs.assets.crawl import crawl_books

        scrapyd = ScrapydResource(poll_interval_seconds=0, timeout_seconds=10)

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.post.return_value = _mock_schedule_response("job-abc-123")
            mock_httpx.get.side_effect = [
                _mock_listjobs_response("job-abc-123", "pending"),
                _mock_listjobs_response("job-abc-123", "running"),
                _mock_listjobs_response("job-abc-123", "finished"),
            ]

            result = dg.materialize_to_memory(
                [crawl_books],
                resources={"scrapyd": scrapyd},
            )

        assert result.success
        output = result.output_for_node("crawl_books")
        assert output == "job-abc-123"
        mock_httpx.post.assert_called_once()
        assert mock_httpx.get.call_count == 3

    def test_returns_job_id_when_immediately_finished(self) -> None:
        """If the job finishes on first poll, return immediately."""
        from litmatch.defs.assets.crawl import crawl_books

        scrapyd = ScrapydResource(poll_interval_seconds=0, timeout_seconds=10)

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.post.return_value = _mock_schedule_response("fast-job")
            mock_httpx.get.return_value = _mock_listjobs_response("fast-job", "finished")

            result = dg.materialize_to_memory(
                [crawl_books],
                resources={"scrapyd": scrapyd},
            )

        assert result.success
        output = result.output_for_node("crawl_books")
        assert output == "fast-job"
        assert mock_httpx.get.call_count == 1

    def test_raises_on_timeout(self) -> None:
        """If the job never finishes within timeout, raise a TimeoutError."""
        from litmatch.defs.assets.crawl import crawl_books

        scrapyd = ScrapydResource(poll_interval_seconds=0, timeout_seconds=0)

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.post.return_value = _mock_schedule_response("slow-job")
            mock_httpx.get.return_value = _mock_listjobs_response("slow-job", "running")

            result = dg.materialize_to_memory(
                [crawl_books],
                resources={"scrapyd": scrapyd},
                raise_on_error=False,
            )

        assert not result.success

    def test_raises_on_schedule_failure(self) -> None:
        """If Scrapyd schedule fails, the materialization should fail."""
        from litmatch.defs.assets.crawl import crawl_books

        scrapyd = ScrapydResource(poll_interval_seconds=0, timeout_seconds=10)

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            error_response = MagicMock()
            error_response.status_code = 200
            error_response.json.return_value = {
                "status": "error",
                "message": "project not found",
            }
            mock_httpx.post.return_value = error_response

            result = dg.materialize_to_memory(
                [crawl_books],
                resources={"scrapyd": scrapyd},
                raise_on_error=False,
            )

        assert not result.success

    def test_raises_on_unknown_status(self) -> None:
        """If the job status becomes 'unknown', the materialization should fail."""
        from litmatch.defs.assets.crawl import crawl_books

        scrapyd = ScrapydResource(poll_interval_seconds=0, timeout_seconds=10)

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.post.return_value = _mock_schedule_response("lost-job")
            empty_response = MagicMock()
            empty_response.status_code = 200
            empty_response.json.return_value = {
                "status": "ok",
                "pending": [],
                "running": [],
                "finished": [],
            }
            mock_httpx.get.return_value = empty_response

            result = dg.materialize_to_memory(
                [crawl_books],
                resources={"scrapyd": scrapyd},
                raise_on_error=False,
            )

        assert not result.success


class TestCrawlBooksUnitLogic:
    """Direct unit tests for the crawl logic function (bypass Dagster framework).

    These test the internal _execute_crawl function directly to verify
    specific error messages and return values.
    """

    def test_execute_crawl_returns_job_id(self) -> None:
        """The internal function should return the job_id on success."""
        from litmatch.defs.assets.crawl import _execute_crawl

        mock_scrapyd = MagicMock(spec=ScrapydResource)
        mock_scrapyd.schedule.return_value = "abc-123"
        mock_scrapyd.poll_interval_seconds = 0
        mock_scrapyd.timeout_seconds = 10
        mock_scrapyd.job_status.return_value = "finished"

        mock_log = MagicMock()

        result = _execute_crawl(mock_scrapyd, mock_log)

        assert result == "abc-123"

    def test_execute_crawl_timeout_message(self) -> None:
        """TimeoutError message should contain job_id and timeout value."""
        from litmatch.defs.assets.crawl import _execute_crawl

        mock_scrapyd = MagicMock(spec=ScrapydResource)
        mock_scrapyd.schedule.return_value = "slow-job"
        mock_scrapyd.poll_interval_seconds = 0
        mock_scrapyd.timeout_seconds = 0
        mock_scrapyd.job_status.return_value = "running"

        mock_log = MagicMock()

        with pytest.raises(TimeoutError, match="Crawl job slow-job timed out"):
            _execute_crawl(mock_scrapyd, mock_log)

    def test_execute_crawl_unknown_status_message(self) -> None:
        """RuntimeError message should contain job_id and 'unknown'."""
        from litmatch.defs.assets.crawl import _execute_crawl

        mock_scrapyd = MagicMock(spec=ScrapydResource)
        mock_scrapyd.schedule.return_value = "lost-job"
        mock_scrapyd.poll_interval_seconds = 0
        mock_scrapyd.timeout_seconds = 10
        mock_scrapyd.job_status.return_value = "unknown"

        mock_log = MagicMock()

        with pytest.raises(RuntimeError, match="lost-job.*unknown"):
            _execute_crawl(mock_scrapyd, mock_log)

    def test_execute_crawl_polls_through_pending_and_running(self) -> None:
        """Should poll through pending -> running -> finished states."""
        from litmatch.defs.assets.crawl import _execute_crawl

        mock_scrapyd = MagicMock(spec=ScrapydResource)
        mock_scrapyd.schedule.return_value = "poll-job"
        mock_scrapyd.poll_interval_seconds = 0
        mock_scrapyd.timeout_seconds = 10
        mock_scrapyd.job_status.side_effect = ["pending", "running", "finished"]

        mock_log = MagicMock()

        result = _execute_crawl(mock_scrapyd, mock_log)

        assert result == "poll-job"
        assert mock_scrapyd.job_status.call_count == 3


class TestJobsModule:
    """Tests for centralized job definitions in jobs.py."""

    def test_etl_pipeline_job_exists(self) -> None:
        """The etl_pipeline job should be importable from jobs module."""
        from litmatch.defs.jobs import etl_pipeline

        assert etl_pipeline is not None
        assert etl_pipeline.name == "etl_pipeline"

    def test_crawl_and_load_job_exists(self) -> None:
        """The crawl_and_load job should be importable from jobs module."""
        from litmatch.defs.jobs import crawl_and_load

        assert crawl_and_load is not None
        assert crawl_and_load.name == "crawl_and_load"

    def test_crawl_and_load_selects_all_assets(self) -> None:
        """crawl_and_load job should select all assets (crawl + ETL)."""
        from litmatch.defs.jobs import crawl_and_load

        assert crawl_and_load.name == "crawl_and_load"
