"""Data freshness sensor: watches books.jsonl for changes and triggers ETL.

This sensor monitors the books.jsonl file's modification time and triggers
the ETL pipeline job when the file has been updated since the last check.
The cursor stores the last-seen mtime as a string for serialization.
"""
import os

import dagster as dg

from litmatch.defs.jobs import etl_pipeline
from litmatch.defs.resources.path import PathResource

CURSOR_KEY = "last_mtime"


@dg.sensor(
    name="data_freshness_sensor",
    job=etl_pipeline,
    minimum_interval_seconds=30,
    description="Watches books.jsonl for modifications and triggers the ETL pipeline.",
    required_resource_keys=set(),
)
def data_freshness_sensor(
    context: dg.SensorEvaluationContext,
    path: PathResource,
) -> dg.SensorResult:
    """Evaluate whether books.jsonl has been modified since the last tick.

    On first run (no cursor), triggers if the file exists.
    On subsequent runs, triggers only if the file's mtime has changed.
    If the file does not exist, skips without error.

    Args:
        context: Dagster sensor evaluation context (provides cursor).
        path: PathResource providing the books.jsonl file path.

    Returns:
        SensorResult with a RunRequest if the file changed, or empty otherwise.
    """
    jsonl_path = path.books_jsonl_path

    if not os.path.exists(jsonl_path):
        context.log.info(f"File not found: {jsonl_path}. Skipping.")
        return dg.SensorResult(run_requests=[], cursor=context.cursor)

    current_mtime = os.path.getmtime(jsonl_path)
    current_mtime_str = str(current_mtime)

    last_mtime_str = context.cursor

    if last_mtime_str is not None and last_mtime_str == current_mtime_str:
        context.log.info("books.jsonl unchanged. Skipping.")
        return dg.SensorResult(run_requests=[], cursor=current_mtime_str)

    context.log.info(
        f"books.jsonl changed (mtime: {current_mtime_str}). Triggering ETL pipeline."
    )
    return dg.SensorResult(
        run_requests=[dg.RunRequest(run_key=current_mtime_str)],
        cursor=current_mtime_str,
    )
