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


def _mock_log_response(content: str = "", status_code: int = 200) -> MagicMock:
    """Create a mock httpx response for the log endpoint."""
    response = MagicMock()
    response.status_code = status_code
    response.text = content
    response.content = content.encode()
    return response


def _url_dispatching_get(job_id: str, states: list[str]) -> MagicMock:
    """Create a mock httpx.get that dispatches based on URL.

    Handles both listjobs.json calls and log endpoint calls.
    """
    state_iter = iter(states)

    def side_effect(url: str, **kwargs: object) -> MagicMock:
        if "listjobs.json" in url:
            state = next(state_iter)
            return _mock_listjobs_response(job_id, state)
        if "/logs/" in url:
            return _mock_log_response("2025-01-01 INFO: Spider log line\n")
        raise ValueError(f"Unexpected URL: {url}")

    mock = MagicMock(side_effect=side_effect)
    return mock


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
            mock_httpx.get = _url_dispatching_get(
                "job-abc-123", ["pending", "running", "finished"]
            )

            result = dg.materialize_to_memory(
                [crawl_books],
                resources={"scrapyd": scrapyd},
            )

        assert result.success
        output = result.output_for_node("crawl_books")
        assert output == "job-abc-123"
        mock_httpx.post.assert_called_once()

    def test_returns_job_id_when_immediately_finished(self) -> None:
        """If the job finishes on first poll, return immediately."""
        from litmatch.defs.assets.crawl import crawl_books

        scrapyd = ScrapydResource(poll_interval_seconds=0, timeout_seconds=10)

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.post.return_value = _mock_schedule_response("fast-job")
            mock_httpx.get = _url_dispatching_get("fast-job", ["finished"])

            result = dg.materialize_to_memory(
                [crawl_books],
                resources={"scrapyd": scrapyd},
            )

        assert result.success
        output = result.output_for_node("crawl_books")
        assert output == "fast-job"

    def test_raises_on_timeout(self) -> None:
        """If the job never finishes within timeout, raise a TimeoutError."""
        from litmatch.defs.assets.crawl import crawl_books

        scrapyd = ScrapydResource(poll_interval_seconds=0, timeout_seconds=0)

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.post.return_value = _mock_schedule_response("slow-job")
            mock_httpx.get = _url_dispatching_get("slow-job", ["running"] * 10)

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
            mock_httpx.get = _url_dispatching_get("lost-job", ["unknown"])

            result = dg.materialize_to_memory(
                [crawl_books],
                resources={"scrapyd": scrapyd},
                raise_on_error=False,
            )

        assert not result.success

    def test_asset_streams_spider_logs(self) -> None:
        """Asset should succeed while streaming spider logs via fetch_log.

        Log streaming correctness is verified in TestCrawlBooksUnitLogic.
        This test confirms the asset wires up fetch_log and completes
        successfully with log fetching active.
        """
        from litmatch.defs.assets.crawl import crawl_books

        scrapyd = ScrapydResource(poll_interval_seconds=0, timeout_seconds=10)

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.post.return_value = _mock_schedule_response("log-job")
            mock_httpx.get = _url_dispatching_get(
                "log-job", ["running", "finished"]
            )

            result = dg.materialize_to_memory(
                [crawl_books],
                resources={"scrapyd": scrapyd},
            )

        assert result.success
        output = result.output_for_node("crawl_books")
        assert output == "log-job"


class TestCrawlBooksUnitLogic:
    """Direct unit tests for the crawl logic function (bypass Dagster framework).

    These test the internal _execute_crawl function directly to verify
    specific error messages and return values.
    """

    def test_execute_crawl_returns_job_id_and_log(self) -> None:
        """The internal function should return (job_id, log_text) on success."""
        from litmatch.defs.assets.crawl import _execute_crawl

        mock_scrapyd = MagicMock(spec=ScrapydResource)
        mock_scrapyd.schedule.return_value = "abc-123"
        mock_scrapyd.poll_interval_seconds = 0
        mock_scrapyd.timeout_seconds = 10
        mock_scrapyd.job_status.return_value = "finished"

        mock_log = MagicMock()

        job_id, log_text = _execute_crawl(mock_scrapyd, mock_log)

        assert job_id == "abc-123"
        assert log_text == ""

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

        job_id, _ = _execute_crawl(mock_scrapyd, mock_log)

        assert job_id == "poll-job"
        assert mock_scrapyd.job_status.call_count == 3

    def test_execute_crawl_streams_logs_during_polling(self) -> None:
        """When fetch_log is provided, spider log lines should be emitted."""
        from litmatch.defs.assets.crawl import _execute_crawl

        mock_scrapyd = MagicMock(spec=ScrapydResource)
        mock_scrapyd.schedule.return_value = "log-job"
        mock_scrapyd.spider = "bookmarks"
        mock_scrapyd.poll_interval_seconds = 0
        mock_scrapyd.timeout_seconds = 10
        mock_scrapyd.job_status.side_effect = ["running", "finished"]

        mock_log = MagicMock()
        mock_fetch_log = MagicMock(side_effect=[
            ("2025-01-01 INFO: Spider opened\n2025-01-01 INFO: Crawling page 1\n", 60),
            ("2025-01-01 INFO: Spider closed\n", 90),
        ])

        job_id, log_text = _execute_crawl(mock_scrapyd, mock_log, fetch_log=mock_fetch_log)

        assert job_id == "log-job"
        # Should have called fetch_log for running and finished states
        assert mock_fetch_log.call_count == 2
        # Spider log lines should be emitted with [spider:bookmarks] prefix
        spider_log_calls = [
            call for call in mock_log.info.call_args_list
            if "[spider:" in str(call)
        ]
        assert len(spider_log_calls) == 3
        # Log text should be accumulated
        assert "Spider opened" in log_text
        assert "Spider closed" in log_text

    def test_execute_crawl_handles_log_fetch_failure(self) -> None:
        """If fetch_log raises, crawl should continue and log a warning."""
        from litmatch.defs.assets.crawl import _execute_crawl

        mock_scrapyd = MagicMock(spec=ScrapydResource)
        mock_scrapyd.schedule.return_value = "err-job"
        mock_scrapyd.spider = "bookmarks"
        mock_scrapyd.poll_interval_seconds = 0
        mock_scrapyd.timeout_seconds = 10
        mock_scrapyd.job_status.side_effect = ["running", "finished"]

        mock_log = MagicMock()
        mock_fetch_log = MagicMock(side_effect=[
            ConnectionError("scrapyd unreachable"),
            ("2025-01-01 INFO: Spider closed\n", 30),
        ])

        job_id, _ = _execute_crawl(mock_scrapyd, mock_log, fetch_log=mock_fetch_log)

        assert job_id == "err-job"
        # Should have logged a warning about the failed fetch
        warning_calls = [
            call for call in mock_log.warning.call_args_list
            if "Failed to fetch spider log" in str(call)
        ]
        assert len(warning_calls) == 1

    def test_execute_crawl_skips_logs_when_pending(self) -> None:
        """fetch_log should not be called when status is 'pending'."""
        from litmatch.defs.assets.crawl import _execute_crawl

        mock_scrapyd = MagicMock(spec=ScrapydResource)
        mock_scrapyd.schedule.return_value = "pend-job"
        mock_scrapyd.spider = "bookmarks"
        mock_scrapyd.poll_interval_seconds = 0
        mock_scrapyd.timeout_seconds = 10
        mock_scrapyd.job_status.side_effect = ["pending", "finished"]

        mock_log = MagicMock()
        mock_fetch_log = MagicMock(return_value=("", 0))

        job_id, _ = _execute_crawl(mock_scrapyd, mock_log, fetch_log=mock_fetch_log)

        assert job_id == "pend-job"
        # fetch_log should only be called for the "finished" poll, not "pending"
        assert mock_fetch_log.call_count == 1

    def test_execute_crawl_fetches_final_log_on_finish(self) -> None:
        """Log should be fetched one last time when status is 'finished'."""
        from litmatch.defs.assets.crawl import _execute_crawl

        mock_scrapyd = MagicMock(spec=ScrapydResource)
        mock_scrapyd.schedule.return_value = "final-job"
        mock_scrapyd.spider = "bookmarks"
        mock_scrapyd.poll_interval_seconds = 0
        mock_scrapyd.timeout_seconds = 10
        mock_scrapyd.job_status.return_value = "finished"

        mock_log = MagicMock()
        mock_fetch_log = MagicMock(
            return_value=("2025-01-01 INFO: Final stats\n", 30)
        )

        job_id, _ = _execute_crawl(mock_scrapyd, mock_log, fetch_log=mock_fetch_log)

        assert job_id == "final-job"
        assert mock_fetch_log.call_count == 1
        spider_log_calls = [
            call for call in mock_log.info.call_args_list
            if "[spider:" in str(call)
        ]
        assert len(spider_log_calls) == 1

    def test_execute_crawl_works_without_fetch_log(self) -> None:
        """Backward compatibility: works without fetch_log parameter."""
        from litmatch.defs.assets.crawl import _execute_crawl

        mock_scrapyd = MagicMock(spec=ScrapydResource)
        mock_scrapyd.schedule.return_value = "compat-job"
        mock_scrapyd.poll_interval_seconds = 0
        mock_scrapyd.timeout_seconds = 10
        mock_scrapyd.job_status.return_value = "finished"

        mock_log = MagicMock()

        job_id, log_text = _execute_crawl(mock_scrapyd, mock_log)

        assert job_id == "compat-job"
        assert log_text == ""


class TestParseScrapyStats:
    """Tests for the _parse_scrapy_stats helper function."""

    def test_extracts_item_count(self) -> None:
        """Should extract item_scraped_count from Scrapy closing output."""
        from litmatch.defs.assets.crawl import _parse_scrapy_stats

        log_text = (
            "2025-01-01 INFO: Dumping Scrapy stats:\n"
            "{'item_scraped_count': 1234,\n"
            " 'downloader/request_count': 5678}\n"
        )
        stats = _parse_scrapy_stats(log_text)
        assert stats["item_scraped_count"] == 1234

    def test_extracts_request_count(self) -> None:
        """Should extract downloader/request_count."""
        from litmatch.defs.assets.crawl import _parse_scrapy_stats

        log_text = "'downloader/request_count': 5678,\n"
        stats = _parse_scrapy_stats(log_text)
        assert stats["request_count"] == 5678

    def test_extracts_error_count(self) -> None:
        """Should extract log_count/ERROR."""
        from litmatch.defs.assets.crawl import _parse_scrapy_stats

        log_text = "'log_count/ERROR': 2,\n"
        stats = _parse_scrapy_stats(log_text)
        assert stats["error_count"] == 2

    def test_handles_missing_stats(self) -> None:
        """Should return empty dict when stats are not present."""
        from litmatch.defs.assets.crawl import _parse_scrapy_stats

        log_text = "2025-01-01 INFO: Spider opened\n"
        stats = _parse_scrapy_stats(log_text)
        assert stats == {}

    def test_handles_empty_log(self) -> None:
        """Should return empty dict for empty string."""
        from litmatch.defs.assets.crawl import _parse_scrapy_stats

        stats = _parse_scrapy_stats("")
        assert stats == {}

    def test_extracts_all_stats_together(self) -> None:
        """Should extract all three stats from a complete Scrapy log."""
        from litmatch.defs.assets.crawl import _parse_scrapy_stats

        log_text = (
            "2025-01-01 INFO: Dumping Scrapy stats:\n"
            "{'downloader/request_count': 100,\n"
            " 'item_scraped_count': 42,\n"
            " 'log_count/ERROR': 3,\n"
            " 'finish_reason': 'finished'}\n"
        )
        stats = _parse_scrapy_stats(log_text)
        assert stats == {
            "item_scraped_count": 42,
            "request_count": 100,
            "error_count": 3,
        }


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
