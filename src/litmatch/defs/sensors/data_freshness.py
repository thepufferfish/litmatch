"""Staging data sensor: watches for new crawl data in the staging table.

Triggers the ETL pipeline when new staging rows appear since the last check.
The cursor stores the latest crawl_job_id that was processed.
"""
import dagster as dg

from litmatch.defs.jobs import etl_pipeline
from litmatch.defs.resources.database import DatabaseResource
from litmatch.defs.utils.staging import ensure_staging_table, get_latest_crawl_job_id


@dg.sensor(
    name="staging_data_sensor",
    job=etl_pipeline,
    minimum_interval_seconds=60,
    description="Watches the staging table for new crawl data and triggers ETL.",
)
def staging_data_sensor(
    context: dg.SensorEvaluationContext,
    database: DatabaseResource,
) -> dg.SensorResult:
    """Check if new crawl data exists in the staging table.

    Queries for the latest crawl_job_id. If it differs from the cursor
    (last processed crawl), triggers a new ETL run.

    Args:
        context: Dagster sensor evaluation context (provides cursor).
        database: DatabaseResource providing the database engine.

    Returns:
        SensorResult with a RunRequest if new data found, or empty otherwise.
    """
    engine = database.get_engine()
    try:
        ensure_staging_table(engine)

        latest_job_id = get_latest_crawl_job_id(engine)

        if latest_job_id is None:
            context.log.info("No data in staging table. Skipping.")
            return dg.SensorResult(run_requests=[], cursor=context.cursor)

        if context.cursor == latest_job_id:
            context.log.info(
                f"Staging data unchanged (job_id={latest_job_id}). Skipping."
            )
            return dg.SensorResult(run_requests=[], cursor=latest_job_id)

        context.log.info(
            f"New staging data detected (job_id={latest_job_id}). "
            "Triggering ETL pipeline."
        )
        return dg.SensorResult(
            run_requests=[dg.RunRequest(run_key=latest_job_id)],
            cursor=latest_job_id,
        )
    finally:
        engine.dispose()
