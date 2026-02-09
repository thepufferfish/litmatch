"""Scrapyd resource for triggering and monitoring scraper runs.

Provides HTTP methods to schedule spiders, check job status,
and verify Scrapyd availability via its JSON API.
"""
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
