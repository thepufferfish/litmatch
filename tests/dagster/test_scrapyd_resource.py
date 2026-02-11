"""Unit tests for the ScrapydResource.

Tests the Scrapyd HTTP client resource that schedules spiders,
checks job status, and lists available spiders.
"""
import json
from unittest.mock import MagicMock, patch

import dagster as dg
import httpx
import pytest

from litmatch.defs.resources.scrapyd import ScrapydResource


class TestScrapydResourceDefinition:
    """Tests that ScrapydResource is properly defined as a Dagster resource."""

    def test_is_configurable_resource(self) -> None:
        """ScrapydResource should be a Dagster ConfigurableResource."""
        assert issubclass(ScrapydResource, dg.ConfigurableResource)

    def test_default_base_url(self) -> None:
        """Default base_url should point to localhost Scrapyd."""
        resource = ScrapydResource()
        assert resource.base_url == "http://localhost:6800"

    def test_default_project(self) -> None:
        """Default project should be 'bookmarks'."""
        resource = ScrapydResource()
        assert resource.project == "bookmarks"

    def test_custom_base_url(self) -> None:
        """base_url should be configurable."""
        resource = ScrapydResource(base_url="http://scrapyd:6800")
        assert resource.base_url == "http://scrapyd:6800"

    def test_custom_project(self) -> None:
        """project should be configurable."""
        resource = ScrapydResource(project="other_project")
        assert resource.project == "other_project"

    def test_default_spider(self) -> None:
        """Default spider should be 'bookmarks'."""
        resource = ScrapydResource()
        assert resource.spider == "bookmarks"

    def test_custom_spider(self) -> None:
        """spider should be configurable."""
        resource = ScrapydResource(spider="custom_spider")
        assert resource.spider == "custom_spider"

    def test_default_poll_interval(self) -> None:
        """Default poll_interval_seconds should be a positive number."""
        resource = ScrapydResource()
        assert resource.poll_interval_seconds > 0

    def test_default_timeout(self) -> None:
        """Default timeout_seconds should be a positive number."""
        resource = ScrapydResource()
        assert resource.timeout_seconds > 0


class TestScrapydSchedule:
    """Tests for the schedule method that triggers a spider crawl."""

    def test_schedule_returns_job_id_on_success(self) -> None:
        """A successful schedule call should return the Scrapyd job ID."""
        resource = ScrapydResource()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "node_name": "scrapyd-node",
            "status": "ok",
            "jobid": "abc123",
        }

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.post.return_value = mock_response
            job_id = resource.schedule()

        assert job_id == "abc123"
        mock_httpx.post.assert_called_once_with(
            "http://localhost:6800/schedule.json",
            data={"project": "bookmarks", "spider": "bookmarks"},
            timeout=30,
        )

    def test_schedule_uses_custom_project_and_spider(self) -> None:
        """Schedule should use the configured project and spider."""
        resource = ScrapydResource(
            base_url="http://custom:6800",
            project="myproject",
            spider="myspider",
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "jobid": "xyz789",
        }

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.post.return_value = mock_response
            job_id = resource.schedule()

        assert job_id == "xyz789"
        mock_httpx.post.assert_called_once_with(
            "http://custom:6800/schedule.json",
            data={"project": "myproject", "spider": "myspider"},
            timeout=30,
        )

    def test_schedule_raises_on_scrapyd_error_status(self) -> None:
        """If Scrapyd returns status != 'ok', raise a RuntimeError."""
        resource = ScrapydResource()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "error",
            "message": "project not found",
        }

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.post.return_value = mock_response
            with pytest.raises(RuntimeError, match="project not found"):
                resource.schedule()

    def test_schedule_raises_on_http_error(self) -> None:
        """If the HTTP request fails, the error should propagate."""
        resource = ScrapydResource()

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.post.side_effect = ConnectionError("connection refused")
            with pytest.raises(ConnectionError, match="connection refused"):
                resource.schedule()

    def test_schedule_raises_on_non_200_status(self) -> None:
        """If Scrapyd returns a non-200 HTTP status, raise an error."""
        resource = ScrapydResource()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("500 Server Error")

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.post.return_value = mock_response
            with pytest.raises(Exception, match="500 Server Error"):
                resource.schedule()


class TestScrapydJobStatus:
    """Tests for the job_status method that checks crawl progress."""

    def test_job_status_returns_running(self) -> None:
        """Should return 'running' when the job is in the running list."""
        resource = ScrapydResource()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "pending": [],
            "running": [{"id": "abc123", "spider": "bookmarks"}],
            "finished": [],
        }

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_response
            status = resource.job_status("abc123")

        assert status == "running"

    def test_job_status_returns_pending(self) -> None:
        """Should return 'pending' when the job is in the pending list."""
        resource = ScrapydResource()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "pending": [{"id": "abc123", "spider": "bookmarks"}],
            "running": [],
            "finished": [],
        }

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_response
            status = resource.job_status("abc123")

        assert status == "pending"

    def test_job_status_returns_finished(self) -> None:
        """Should return 'finished' when the job is in the finished list."""
        resource = ScrapydResource()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "pending": [],
            "running": [],
            "finished": [{"id": "abc123", "spider": "bookmarks"}],
        }

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_response
            status = resource.job_status("abc123")

        assert status == "finished"

    def test_job_status_returns_unknown_when_not_found(self) -> None:
        """Should return 'unknown' when the job is not in any list."""
        resource = ScrapydResource()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "pending": [],
            "running": [],
            "finished": [],
        }

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_response
            status = resource.job_status("nonexistent")

        assert status == "unknown"

    def test_job_status_calls_correct_endpoint(self) -> None:
        """Should call the listjobs.json endpoint with the project param."""
        resource = ScrapydResource(
            base_url="http://scrapyd:6800",
            project="myproject",
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "pending": [],
            "running": [],
            "finished": [],
        }

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_response
            resource.job_status("abc123")

        mock_httpx.get.assert_called_once_with(
            "http://scrapyd:6800/listjobs.json",
            params={"project": "myproject"},
            timeout=30,
        )

    def test_job_status_raises_on_http_error(self) -> None:
        """If the HTTP request fails, the error should propagate."""
        resource = ScrapydResource()

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.get.side_effect = ConnectionError("connection refused")
            with pytest.raises(ConnectionError, match="connection refused"):
                resource.job_status("abc123")


class TestScrapydIsHealthy:
    """Tests for the is_healthy method that checks Scrapyd availability."""

    def test_healthy_returns_true(self) -> None:
        """Should return True when Scrapyd responds with 200."""
        resource = ScrapydResource()
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_response
            assert resource.is_healthy() is True

    def test_unhealthy_returns_false_on_connection_error(self) -> None:
        """Should return False when Scrapyd is unreachable."""
        resource = ScrapydResource()

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.get.side_effect = ConnectionError("refused")
            assert resource.is_healthy() is False

    def test_unhealthy_returns_false_on_non_200(self) -> None:
        """Should return False when Scrapyd returns non-200 status."""
        resource = ScrapydResource()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = Exception("500 error")

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_response
            assert resource.is_healthy() is False

    def test_healthy_calls_correct_endpoint(self) -> None:
        """Should GET the Scrapyd daemonstatus.json endpoint."""
        resource = ScrapydResource(base_url="http://custom:6800")
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_response
            resource.is_healthy()

        mock_httpx.get.assert_called_once_with(
            "http://custom:6800/daemonstatus.json",
            timeout=10,
        )


class TestScrapydFetchLog:
    """Tests for the fetch_log method that retrieves spider log content."""

    def test_fetch_log_returns_content_and_offset(self) -> None:
        """Happy path: returns full log content and correct new offset."""
        resource = ScrapydResource()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "2025-01-01 INFO: Crawl started\n"
        mock_response.content = b"2025-01-01 INFO: Crawl started\n"

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_response
            content, new_offset = resource.fetch_log("a" * 32)

        assert content == "2025-01-01 INFO: Crawl started\n"
        assert new_offset == len(b"2025-01-01 INFO: Crawl started\n")

    def test_fetch_log_with_offset_sends_range_header(self) -> None:
        """When offset > 0, should send Range header for incremental fetch."""
        resource = ScrapydResource()
        mock_response = MagicMock()
        mock_response.status_code = 206
        mock_response.text = "new log line\n"
        mock_response.content = b"new log line\n"

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_response
            content, new_offset = resource.fetch_log("b" * 32, offset=100)

        call_kwargs = mock_httpx.get.call_args
        assert call_kwargs.kwargs["headers"]["Range"] == "bytes=100-"
        assert content == "new log line\n"
        assert new_offset == 100 + len(b"new log line\n")

    def test_fetch_log_returns_empty_on_404(self) -> None:
        """Log not available yet (spider pending) should return empty."""
        resource = ScrapydResource()
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_response
        )

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.HTTPStatusError = httpx.HTTPStatusError
            mock_httpx.get.return_value = mock_response
            content, new_offset = resource.fetch_log("a" * 32)

        assert content == ""
        assert new_offset == 0

    def test_fetch_log_returns_empty_on_416(self) -> None:
        """No new content (Range Not Satisfiable) should return empty."""
        resource = ScrapydResource()
        mock_response = MagicMock()
        mock_response.status_code = 416
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Range Not Satisfiable", request=MagicMock(), response=mock_response
        )

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.HTTPStatusError = httpx.HTTPStatusError
            mock_httpx.get.return_value = mock_response
            content, new_offset = resource.fetch_log("c" * 32, offset=500)

        assert content == ""
        assert new_offset == 500

    def test_fetch_log_builds_correct_url(self) -> None:
        """Should construct URL with project/spider/job_id."""
        resource = ScrapydResource(
            base_url="http://scrapyd:6800",
            project="myproject",
            spider="myspider",
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = ""
        mock_response.content = b""

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.get.return_value = mock_response
            resource.fetch_log("d" * 32)

        call_args = mock_httpx.get.call_args
        assert call_args.args[0] == f"http://scrapyd:6800/logs/myproject/myspider/{'d' * 32}.log"

    def test_fetch_log_raises_on_server_error(self) -> None:
        """HTTP 500 should propagate as an exception."""
        resource = ScrapydResource()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.HTTPStatusError = httpx.HTTPStatusError
            mock_httpx.get.return_value = mock_response
            with pytest.raises(httpx.HTTPStatusError):
                resource.fetch_log("a" * 32)

    def test_fetch_log_rejects_invalid_job_id(self) -> None:
        """Should raise ValueError for non-hex job IDs (path traversal defense)."""
        resource = ScrapydResource()
        with pytest.raises(ValueError, match="Invalid job_id format"):
            resource.fetch_log("../../etc/passwd")

    def test_fetch_log_rejects_negative_offset(self) -> None:
        """Should raise ValueError for negative offset."""
        resource = ScrapydResource()
        with pytest.raises(ValueError, match="offset must be non-negative"):
            resource.fetch_log("a" * 32, offset=-1)


class TestScrapydCancel:
    """Tests for the cancel method that cancels running Scrapyd jobs."""

    def test_cancel_posts_to_cancel_endpoint(self) -> None:
        """Should POST to /cancel.json with project and job params."""
        resource = ScrapydResource()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "prevstate": "running",
        }

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.post.return_value = mock_response
            resource.cancel("abc123")

        mock_httpx.post.assert_called_once_with(
            "http://localhost:6800/cancel.json",
            data={"project": "bookmarks", "job": "abc123"},
            timeout=30,
        )

    def test_cancel_uses_custom_project(self) -> None:
        """Should use the configured project name in the cancel request."""
        resource = ScrapydResource(
            base_url="http://scrapyd:6800",
            project="myproject",
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "prevstate": "running",
        }

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.post.return_value = mock_response
            resource.cancel("xyz789")

        mock_httpx.post.assert_called_once_with(
            "http://scrapyd:6800/cancel.json",
            data={"project": "myproject", "job": "xyz789"},
            timeout=30,
        )

    def test_cancel_returns_prevstate(self) -> None:
        """Should return the previous state from Scrapyd response."""
        resource = ScrapydResource()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "ok",
            "prevstate": "running",
        }

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.post.return_value = mock_response
            prevstate = resource.cancel("abc123")

        assert prevstate == "running"

    def test_cancel_raises_on_scrapyd_error(self) -> None:
        """If Scrapyd returns status != 'ok', raise RuntimeError."""
        resource = ScrapydResource()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "error",
            "message": "job not found",
        }

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.post.return_value = mock_response
            with pytest.raises(RuntimeError, match="job not found"):
                resource.cancel("abc123")

    def test_cancel_raises_on_http_error(self) -> None:
        """If the HTTP request fails, the error should propagate."""
        resource = ScrapydResource()

        with patch("litmatch.defs.resources.scrapyd.httpx") as mock_httpx:
            mock_httpx.post.side_effect = ConnectionError("connection refused")
            with pytest.raises(ConnectionError, match="connection refused"):
                resource.cancel("abc123")
