"""Startup crawl sensor: fires once on first deployment to trigger a crawl.

This sensor implements a state machine that triggers the crawl_and_load
job exactly once when Scrapyd is healthy on first deployment. It replaces
the old startup_etl_sensor by including the crawl step.

State machine (tracked via cursor):
  None (initial)       -> check Scrapyd health -> "crawl_requested"
  "crawl_requested"    -> transition to done   -> "completed"
  "completed"          -> permanent terminal state

If Scrapyd is unhealthy on the first tick, the sensor retries on the
next tick (cursor stays None).
"""
import dagster as dg

from litmatch.defs.jobs import crawl_job
from litmatch.defs.resources.scrapyd import ScrapydResource

CURSOR_CRAWL_REQUESTED = "crawl_requested"
CURSOR_COMPLETED = "completed"


@dg.sensor(
    name="startup_crawl_sensor",
    job=crawl_job,
    minimum_interval_seconds=30,
    description=(
        "Fires exactly once on first deployment when Scrapyd is healthy, "
        "triggering a full crawl-and-load pipeline to seed the database."
    ),
    required_resource_keys=set(),
)
def startup_crawl_sensor(
    context: dg.SensorEvaluationContext,
    scrapyd: ScrapydResource,
) -> dg.SensorResult:
    """Evaluate whether to trigger the startup crawl pipeline.

    State transitions:
    - No cursor: Check Scrapyd health. If healthy, request a run and set
      cursor to "crawl_requested". If unhealthy, skip (retry next tick).
    - "crawl_requested": The crawl job was submitted. Transition to
      "completed" (the job itself handles polling for crawl completion).
    - "completed": Terminal state. Do nothing.

    Args:
        context: Dagster sensor evaluation context (provides cursor).
        scrapyd: ScrapydResource for health checking.

    Returns:
        SensorResult with a RunRequest on first healthy tick, or empty otherwise.
    """
    cursor = context.cursor

    # Terminal state: already completed
    if cursor == CURSOR_COMPLETED:
        context.log.info("Startup crawl already completed. Skipping.")
        return dg.SensorResult(run_requests=[], cursor=CURSOR_COMPLETED)

    # Transition: crawl was requested, now mark completed
    if cursor == CURSOR_CRAWL_REQUESTED:
        context.log.info(
            "Crawl job was requested. Transitioning to completed."
        )
        return dg.SensorResult(run_requests=[], cursor=CURSOR_COMPLETED)

    # Initial state (no cursor): check Scrapyd health and trigger
    if not scrapyd.is_healthy():
        context.log.info(
            "Scrapyd is not healthy yet. Will retry on next tick."
        )
        return dg.SensorResult(run_requests=[], cursor=None)

    context.log.info(
        "Scrapyd is healthy. Triggering startup crawl-and-load pipeline."
    )
    return dg.SensorResult(
        run_requests=[dg.RunRequest(run_key="startup_crawl")],
        cursor=CURSOR_CRAWL_REQUESTED,
    )
