"""Unit tests for the crawl_books asset.

The crawl_books asset schedules a Scrapyd spider crawl (fire-and-forget)
and returns the job_id immediately.  The staging_data_sensor handles
detecting when scraped data lands in the staging table.
"""
from unittest.mock import MagicMock, patch

import dagster as dg

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


class TestCrawlBooksExecution:
    """Tests for crawl_books fire-and-forget execution."""

    def test_schedules_and_returns_job_id(self) -> None:
        """Should schedule a crawl and return the job_id immediately."""
        from litmatch.defs.assets.crawl import crawl_books

        scrapyd = ScrapydResource()

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.post.return_value = _mock_schedule_response("job-abc-123")

            result = dg.materialize_to_memory(
                [crawl_books],
                resources={"scrapyd": scrapyd},
            )

        assert result.success
        output = result.output_for_node("crawl_books")
        assert output == "job-abc-123"
        mock_httpx.post.assert_called_once()

    def test_emits_job_id_metadata(self) -> None:
        """Output metadata should contain the job_id."""
        from litmatch.defs.assets.crawl import crawl_books

        scrapyd = ScrapydResource()

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.post.return_value = _mock_schedule_response("meta-job")

            result = dg.materialize_to_memory(
                [crawl_books],
                resources={"scrapyd": scrapyd},
            )

        assert result.success
        event = result.asset_materializations_for_node("crawl_books")[0]
        metadata = dict(event.metadata)
        assert "job_id" in metadata

    def test_raises_on_schedule_failure(self) -> None:
        """If Scrapyd schedule fails, the materialization should fail."""
        from litmatch.defs.assets.crawl import crawl_books

        scrapyd = ScrapydResource()

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

    def test_raises_on_connection_error(self) -> None:
        """If Scrapyd is unreachable, the materialization should fail."""
        from litmatch.defs.assets.crawl import crawl_books

        scrapyd = ScrapydResource()

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.post.side_effect = ConnectionError("scrapyd unreachable")

            result = dg.materialize_to_memory(
                [crawl_books],
                resources={"scrapyd": scrapyd},
                raise_on_error=False,
            )

        assert not result.success

    def test_does_not_poll_or_wait(self) -> None:
        """Fire-and-forget: should not call job_status or sleep."""
        from litmatch.defs.assets.crawl import crawl_books

        scrapyd = ScrapydResource()

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.post.return_value = _mock_schedule_response("fast-job")

            result = dg.materialize_to_memory(
                [crawl_books],
                resources={"scrapyd": scrapyd},
            )

        assert result.success
        # Only POST (schedule) should be called, no GET (listjobs/status)
        mock_httpx.get.assert_not_called()


class TestJobsModule:
    """Tests for centralized job definitions in jobs.py."""

    def test_etl_pipeline_job_exists(self) -> None:
        """The etl_pipeline job should be importable from jobs module."""
        from litmatch.defs.jobs import etl_pipeline

        assert etl_pipeline is not None
        assert etl_pipeline.name == "etl_pipeline"

    def test_crawl_job_exists(self) -> None:
        """The crawl job should be importable from jobs module."""
        from litmatch.defs.jobs import crawl_job

        assert crawl_job is not None
        assert crawl_job.name == "crawl"

    def test_crawl_job_selects_crawl_books(self) -> None:
        """crawl job should select the crawl_books asset."""
        from litmatch.defs.jobs import crawl_job

        selection_str = str(crawl_job.selection)
        assert "crawl_books" in selection_str
