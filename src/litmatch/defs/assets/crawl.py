"""Crawl asset: schedules a Scrapyd spider run and waits for completion.

This asset is the entry point of the crawl-and-load pipeline. It triggers
the bookmarks spider via Scrapyd, polls for completion, and produces
the job_id as output for downstream assets to depend on.
"""
import time
from typing import Protocol

import dagster as dg

from litmatch.defs.resources.scrapyd import ScrapydResource


class _Logger(Protocol):
    """Minimal logger interface for the crawl execution function."""

    def info(self, msg: str) -> None: ...


def _execute_crawl(scrapyd: ScrapydResource, log: _Logger) -> str:
    """Schedule and monitor a Scrapyd spider crawl.

    This is the core logic extracted from the Dagster asset to enable
    direct unit testing without the Dagster framework overhead.

    Args:
        scrapyd: ScrapydResource providing the Scrapyd HTTP client.
        log: Logger instance for status messages.

    Returns:
        The Scrapyd job ID string.

    Raises:
        TimeoutError: If the crawl does not finish within the configured timeout.
        RuntimeError: If the job status becomes 'unknown' (lost by Scrapyd).
    """
    job_id = scrapyd.schedule()
    log.info(f"Scheduled crawl job: {job_id}")

    deadline = time.monotonic() + scrapyd.timeout_seconds

    while True:
        status = scrapyd.job_status(job_id)
        log.info(f"Crawl job {job_id} status: {status}")

        if status == "finished":
            log.info(f"Crawl job {job_id} completed successfully.")
            return job_id

        if status == "unknown":
            raise RuntimeError(
                f"Crawl job {job_id} lost by Scrapyd (status: unknown). "
                "The job may have been cancelled or expired."
            )

        if time.monotonic() >= deadline:
            raise TimeoutError(
                f"Crawl job {job_id} timed out after "
                f"{scrapyd.timeout_seconds} seconds."
            )

        time.sleep(scrapyd.poll_interval_seconds)


@dg.asset(
    description="Schedule a Scrapyd spider crawl and wait for it to finish.",
    kinds={"python", "scrapyd"},
)
def crawl_books(
    context: dg.AssetExecutionContext,
    scrapyd: ScrapydResource,
) -> str:
    """Schedule and monitor a Scrapyd spider crawl.

    Delegates to _execute_crawl for the core polling logic.

    Args:
        context: Dagster asset execution context for logging.
        scrapyd: ScrapydResource providing the Scrapyd HTTP client.

    Returns:
        The Scrapyd job ID string.
    """
    return _execute_crawl(scrapyd, context.log)
