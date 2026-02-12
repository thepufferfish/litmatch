"""Crawl asset: schedules a Scrapyd spider run (fire-and-forget).

This asset triggers the bookmarks spider via Scrapyd and returns
immediately with the job_id.  The spider writes scraped items to the
``raw_books_staging`` table; the ``staging_data_sensor`` detects new
rows and triggers the ETL pipeline automatically.
"""
import dagster as dg

from litmatch.defs.resources.scrapyd import ScrapydResource


@dg.asset(
    description="Schedule a Scrapyd spider crawl (fire-and-forget).",
    kinds={"python", "scrapyd"},
)
def crawl_books(
    context: dg.AssetExecutionContext,
    scrapyd: ScrapydResource,
) -> dg.Output[str]:
    """Schedule a Scrapyd spider crawl and return immediately.

    The crawl runs asynchronously on Scrapyd.  Progress is visible in
    the Scrapyd UI (port 6800).  When the spider finishes, scraped items
    land in the staging table and ``staging_data_sensor`` triggers the
    ETL pipeline.

    Args:
        context: Dagster asset execution context for logging.
        scrapyd: ScrapydResource providing the Scrapyd HTTP client.

    Returns:
        Output containing the Scrapyd job ID string with metadata.
    """
    job_id = scrapyd.schedule()
    context.log.info(f"Scheduled crawl job: {job_id}")
    return dg.Output(job_id, metadata={"job_id": job_id})
