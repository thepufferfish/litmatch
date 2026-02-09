"""Unit tests for the ScrapydResource.

Tests the Scrapyd HTTP client resource that schedules spiders,
checks job status, and lists available spiders.
"""
import json
from unittest.mock import MagicMock, patch

import dagster as dg
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
