"""Extract asset: reads raw scraped data from the PostgreSQL staging table.

This is the first asset in the ETL pipeline. It reads items from the
raw_books_staging table for the most recent crawl.

When used in the crawl job, this asset depends on crawl_books
to ensure the spider finishes writing to the staging table before
extraction begins.
"""
import dagster as dg

from litmatch.defs.resources.database import DatabaseResource
from litmatch.defs.utils.staging import (
    ensure_staging_table,
    fetch_latest_staged_items,
)


@dg.asset(
    description="Raw book records extracted from the staging table",
    kinds={"python", "postgres"},
    deps=["crawl_books"],
)
def raw_books(
    context: dg.AssetExecutionContext,
    database: DatabaseResource,
) -> dg.Output[list[dict]]:
    """Read raw book records from the staging table.

    Queries the raw_books_staging table for items from the most recent
    crawl job. The staging table is created if it does not exist.

    This asset depends on crawl_books when used in the crawl job,
    ensuring the spider completes before extraction begins. In the etl_pipeline
    job (which excludes crawl_books), this asset runs independently.

    Args:
        context: Dagster asset execution context for logging.
        database: DatabaseResource providing a SQLAlchemy engine.
    """
    engine = database.get_engine()
    try:
        ensure_staging_table(engine)
        crawl_job_id, data = fetch_latest_staged_items(engine)

        context.log.info(
            f"Extracted {len(data)} records from staging table "
            f"(crawl_job_id={crawl_job_id!r})"
        )

        if not data:
            context.log.warning(
                "No records found in staging table. "
                "Has the crawl spider run and written to raw_books_staging?"
            )

        return dg.Output(
            data,
            metadata={
                "record_count": len(data),
                "crawl_job_id": crawl_job_id,
            },
        )
    finally:
        engine.dispose()
