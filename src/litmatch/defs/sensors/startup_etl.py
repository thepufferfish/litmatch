"""Startup ETL sensor: fires once on first deployment to seed the database.

This sensor triggers the ETL pipeline exactly once when books.jsonl exists
and the database has not yet been seeded. Uses a cursor value of "seeded"
to prevent re-runs on daemon restarts.
"""
import os

import dagster as dg

from litmatch.defs.resources.path import PathResource
from litmatch.defs.sensors.data_freshness import etl_pipeline

CURSOR_SEEDED = "seeded"


@dg.sensor(
    name="startup_etl_sensor",
    job=etl_pipeline,
    minimum_interval_seconds=30,
    description=(
        "Fires exactly once on first deployment if books.jsonl exists, "
        "seeding the database with initial book data."
    ),
    required_resource_keys=set(),
)
def startup_etl_sensor(
    context: dg.SensorEvaluationContext,
    path: PathResource,
) -> dg.SensorResult:
    """Evaluate whether the database needs initial seeding.

    On first evaluation (no cursor), triggers if books.jsonl exists.
    Once triggered, sets cursor to "seeded" to prevent future runs.
    If the file does not exist, skips without setting the cursor so
    it retries on the next tick.

    Args:
        context: Dagster sensor evaluation context (provides cursor).
        path: PathResource providing the books.jsonl file path.

    Returns:
        SensorResult with a RunRequest on first seed, or empty otherwise.
    """
    if context.cursor == CURSOR_SEEDED:
        context.log.info("Database already seeded. Skipping.")
        return dg.SensorResult(run_requests=[], cursor=CURSOR_SEEDED)

    jsonl_path = path.books_jsonl_path

    if not os.path.exists(jsonl_path):
        context.log.info(
            f"File not found: {jsonl_path}. "
            "Will retry on next tick."
        )
        return dg.SensorResult(run_requests=[], cursor=context.cursor)

    context.log.info(
        f"Found {jsonl_path}. Triggering initial ETL seed."
    )
    return dg.SensorResult(
        run_requests=[dg.RunRequest(run_key="startup_seed")],
        cursor=CURSOR_SEEDED,
    )
