"""Staging data sensor: watches for new crawl data in the staging table.

Triggers the ETL pipeline when new staging rows appear since the last check.

The cursor stores both crawl_job_id and max_id in the format "{job_id}:{max_id}",
enabling incremental processing during long-running crawls.
"""
import dagster as dg

from litmatch.defs.jobs import etl_pipeline
from litmatch.defs.resources.database import DatabaseResource
from litmatch.defs.utils.staging import get_staging_data_state


def _parse_cursor(cursor: str | None) -> tuple[str | None, int]:
    """Parse cursor into (job_id, max_id).

    Supports both legacy format (just job_id) and new format (job_id:max_id).
    Legacy cursors are treated as max_id=0 to trigger on any new data.

    Args:
        cursor: Cursor string in format "job_id:max_id" or legacy "job_id".

    Returns:
        Tuple of (job_id, max_id). Returns (None, 0) if cursor is None.
    """
    if cursor is None:
        return (None, 0)

    if ":" in cursor:
        # New format: "job_id:max_id"
        parts = cursor.rsplit(":", 1)
        return (parts[0], int(parts[1]))
    else:
        # Legacy format: just "job_id" (treat as max_id=0)
        return (cursor, 0)


@dg.sensor(
    name="staging_data_sensor",
    job=etl_pipeline,
    minimum_interval_seconds=60,
    description="Watches the staging table for new crawl data and triggers ETL.",
    default_status=dg.DefaultSensorStatus.RUNNING,
)
def staging_data_sensor(
    context: dg.SensorEvaluationContext,
    database: DatabaseResource,
) -> dg.SensorResult:
    """Check if new crawl data exists in the staging table.

    Tracks both crawl_job_id and max_id to enable incremental processing
    during long-running crawls. Triggers ETL when:
    - A new crawl_job_id appears, OR
    - New rows (higher max_id) appear for the same crawl_job_id

    Args:
        context: Dagster sensor evaluation context (provides cursor).
        database: DatabaseResource providing the database engine.

    Returns:
        SensorResult with a RunRequest if new data found, or empty otherwise.
    """
    engine = database.get_engine()
    try:
        state = get_staging_data_state(engine)

        if state is None:
            context.log.info("No data in staging table. Skipping.")
            return dg.SensorResult(run_requests=[], cursor=None)

        # Parse cursor to get last processed job_id and max_id
        cursor_job_id, cursor_max_id = _parse_cursor(context.cursor)

        # Check if we have new data:
        # 1. Different job_id (new crawl started), OR
        # 2. Same job_id but higher max_id (new rows in ongoing crawl)
        has_new_data = (
            cursor_job_id != state.crawl_job_id
            or cursor_max_id < state.max_id
        )

        if not has_new_data:
            context.log.info(
                f"Staging data unchanged "
                f"(job_id={state.crawl_job_id}, max_id={state.max_id}). "
                "Skipping."
            )
            new_cursor = f"{state.crawl_job_id}:{state.max_id}"
            return dg.SensorResult(run_requests=[], cursor=new_cursor)

        context.log.info(
            f"New staging data detected "
            f"(job_id={state.crawl_job_id}, max_id={state.max_id}, "
            f"row_count={state.row_count}). "
            "Triggering ETL pipeline."
        )
        new_cursor = f"{state.crawl_job_id}:{state.max_id}"
        return dg.SensorResult(
            run_requests=[dg.RunRequest(run_key=new_cursor)],
            cursor=new_cursor,
        )
    finally:
        engine.dispose()
