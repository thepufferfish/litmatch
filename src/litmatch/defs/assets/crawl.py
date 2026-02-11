"""Crawl asset: schedules a Scrapyd spider run and waits for completion.

This asset is the entry point of the crawl-and-load pipeline. It triggers
the bookmarks spider via Scrapyd, polls for completion, and produces
the job_id as output for downstream assets to depend on.
"""
import re
import time
from typing import Protocol

import dagster as dg

from litmatch.defs.resources.scrapyd import ScrapydResource


class _Logger(Protocol):
    """Minimal logger interface for the crawl execution function."""

    def info(self, msg: str) -> None: ...
    def warning(self, msg: str) -> None: ...


class _LogFetcher(Protocol):
    """Callable that fetches new log content from a given offset."""

    def __call__(self, job_id: str, offset: int) -> tuple[str, int]: ...


_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MAX_LOG_LINE_LEN = 2000

_STAT_PATTERNS: dict[str, re.Pattern[str]] = {
    "item_scraped_count": re.compile(r"'item_scraped_count':\s*(\d+)"),
    "request_count": re.compile(r"'downloader/request_count':\s*(\d+)"),
    "error_count": re.compile(r"'log_count/ERROR':\s*(\d+)"),
}


def _parse_scrapy_stats(log_text: str) -> dict[str, int]:
    """Extract key statistics from Scrapy's closing log output.

    Parses the stats dump that Scrapy emits when a spider closes.
    Returns only the stats that are found; missing stats are omitted.

    Args:
        log_text: Raw spider log text to parse.

    Returns:
        Dict with available stats: item_scraped_count, request_count, error_count.
    """
    stats: dict[str, int] = {}
    for key, pattern in _STAT_PATTERNS.items():
        match = pattern.search(log_text)
        if match:
            stats[key] = int(match.group(1))
    return stats


def _execute_crawl(
    scrapyd: ScrapydResource,
    log: _Logger,
    fetch_log: _LogFetcher | None = None,
) -> tuple[str, str]:
    """Schedule and monitor a Scrapyd spider crawl.

    This is the core logic extracted from the Dagster asset to enable
    direct unit testing without the Dagster framework overhead.

    Args:
        scrapyd: ScrapydResource providing the Scrapyd HTTP client.
        log: Logger instance for status messages.
        fetch_log: Optional callable to fetch spider log content
            incrementally. When provided, spider log lines are
            streamed to the logger during polling.

    Returns:
        Tuple of (job_id, accumulated_log_text).

    Raises:
        TimeoutError: If the crawl does not finish within the configured timeout.
        RuntimeError: If the job status becomes 'unknown' (lost by Scrapyd).
    """
    job_id = scrapyd.schedule()
    log.info(f"Scheduled crawl job: {job_id}")

    deadline = time.monotonic() + scrapyd.timeout_seconds
    log_offset = 0
    accumulated_log: list[str] = []

    while True:
        status = scrapyd.job_status(job_id)
        log.info(f"Crawl job {job_id} status: {status}")

        if fetch_log is not None and status in ("running", "finished"):
            try:
                new_content, log_offset = fetch_log(job_id, log_offset)
                if new_content:
                    accumulated_log.append(new_content)
                    for line in new_content.strip().splitlines():
                        sanitized = _CONTROL_CHARS.sub("", line)[:_MAX_LOG_LINE_LEN]
                        log.info(f"[spider:{scrapyd.spider}] {sanitized}")
            except Exception as exc:
                log.warning(f"Failed to fetch spider log: {exc}")

        if status == "finished":
            log.info(f"Crawl job {job_id} completed successfully.")
            return (job_id, "".join(accumulated_log))

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
    tags={"dagster/max_runtime": 5*24*3600} # runs could take 5 days
)
def crawl_books(
    context: dg.AssetExecutionContext,
    scrapyd: ScrapydResource,
) -> dg.Output[str]:
    """Schedule and monitor a Scrapyd spider crawl.

    Delegates to _execute_crawl for the core polling logic.

    Args:
        context: Dagster asset execution context for logging.
        scrapyd: ScrapydResource providing the Scrapyd HTTP client.

    Returns:
        Output containing the Scrapyd job ID string with metadata.
    """
    job_id, log_text = _execute_crawl(
        scrapyd, context.log, fetch_log=scrapyd.fetch_log
    )
    metadata: dict[str, str | int] = {"job_id": job_id, **_parse_scrapy_stats(log_text)}
    return dg.Output(job_id, metadata=metadata)
