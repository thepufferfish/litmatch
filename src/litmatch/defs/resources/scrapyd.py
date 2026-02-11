"""Scrapyd resource for triggering and monitoring scraper runs.

Provides HTTP methods to schedule spiders, check job status,
and verify Scrapyd availability via its JSON API.
"""
import re

import httpx

import dagster as dg


class ScrapydResource(dg.ConfigurableResource):
    """Dagster resource for Scrapyd spider management.

    Configures the Scrapyd API endpoint for scheduling and
    monitoring spider runs.

    Args:
        base_url: Scrapyd HTTP API base URL.
        project: Scrapyd project name (must match egg deployment).
        spider: Spider name to schedule.
        poll_interval_seconds: Seconds between job status polls.
        timeout_seconds: Maximum seconds to wait for a crawl to finish.
    """

    base_url: str = "http://localhost:6800"
    project: str = "bookmarks"
    spider: str = "bookmarks"
    poll_interval_seconds: int = 30
    timeout_seconds: int = 3600

    def schedule(self) -> str:
        """Schedule a spider crawl on Scrapyd.

        Posts to the /schedule.json endpoint to start a new crawl job.

        Returns:
            The Scrapyd job ID string.

        Raises:
            RuntimeError: If Scrapyd returns a non-ok status.
            ConnectionError: If Scrapyd is unreachable.
        """
        response = httpx.post(
            f"{self.base_url}/schedule.json",
            data={"project": self.project, "spider": self.spider},
            timeout=30,
        )
        response.raise_for_status()

        body = response.json()
        if body.get("status") != "ok":
            message = body.get("message", "unknown error")
            raise RuntimeError(
                f"Scrapyd schedule failed: {message}"
            )

        return body["jobid"]

    def job_status(self, job_id: str) -> str:
        """Check the status of a Scrapyd job.

        Queries the /listjobs.json endpoint and searches for the
        given job_id in the pending, running, and finished lists.

        Args:
            job_id: The Scrapyd job ID to look up.

        Returns:
            One of 'pending', 'running', 'finished', or 'unknown'.

        Raises:
            ConnectionError: If Scrapyd is unreachable.
        """
        response = httpx.get(
            f"{self.base_url}/listjobs.json",
            params={"project": self.project},
            timeout=30,
        )
        response.raise_for_status()

        body = response.json()

        for state in ("pending", "running", "finished"):
            jobs = body.get(state, [])
            if any(job.get("id") == job_id for job in jobs):
                return state

        return "unknown"

    def cancel(self, job_id: str) -> str:
        """Cancel a running or pending Scrapyd job.

        Posts to the /cancel.json endpoint to stop a job.

        Args:
            job_id: The Scrapyd job ID to cancel.

        Returns:
            The previous state of the job ('running', 'pending', etc.).

        Raises:
            RuntimeError: If Scrapyd returns a non-ok status.
            ConnectionError: If Scrapyd is unreachable.
        """
        response = httpx.post(
            f"{self.base_url}/cancel.json",
            data={"project": self.project, "job": job_id},
            timeout=30,
        )
        response.raise_for_status()

        body = response.json()
        if body.get("status") != "ok":
            message = body.get("message", "unknown error")
            raise RuntimeError(f"Scrapyd cancel failed: {message}")

        return body.get("prevstate", "unknown")

    _JOB_ID_PATTERN: re.Pattern[str] = re.compile(r"^[a-f0-9]{32}$")
    _MAX_LOG_CHUNK_BYTES: int = 10 * 1024 * 1024  # 10 MB

    def fetch_log(self, job_id: str, offset: int = 0) -> tuple[str, int]:
        """Fetch spider log content from Scrapyd, starting at byte offset.

        Retrieves the raw log file for a specific spider job. Uses HTTP
        Range header to fetch only new content since the last read.

        Args:
            job_id: The Scrapyd job ID (32-char hex string).
            offset: Byte offset to start reading from (0 = beginning).

        Returns:
            Tuple of (log_content, new_offset) where new_offset is the
            byte position after the fetched content.

        Raises:
            ValueError: If job_id format is invalid or offset is negative.
            httpx.HTTPStatusError: If the log endpoint returns an error
                other than 404 or 416.
        """
        if not self._JOB_ID_PATTERN.match(job_id):
            raise ValueError(f"Invalid job_id format: {job_id!r}")
        if offset < 0:
            raise ValueError(f"offset must be non-negative, got {offset}")

        url = f"{self.base_url}/logs/{self.project}/{self.spider}/{job_id}.log"
        headers: dict[str, str] = {}
        if offset > 0:
            headers["Range"] = f"bytes={offset}-"

        response = httpx.get(url, headers=headers, timeout=30)

        if response.status_code in (404, 416):
            return ("", offset)

        response.raise_for_status()

        content_bytes = response.content
        if len(content_bytes) > self._MAX_LOG_CHUNK_BYTES:
            content_bytes = content_bytes[:self._MAX_LOG_CHUNK_BYTES]

        return (
            content_bytes.decode("utf-8", errors="replace"),
            offset + len(content_bytes),
        )

    def is_healthy(self) -> bool:
        """Check if Scrapyd is reachable and responding.

        Calls the /daemonstatus.json endpoint. Returns True if
        Scrapyd responds with HTTP 200, False otherwise.

        Returns:
            True if Scrapyd is healthy, False otherwise.
        """
        try:
            response = httpx.get(
                f"{self.base_url}/daemonstatus.json",
                timeout=10,
            )
            response.raise_for_status()
            return True
        except Exception:
            return False
