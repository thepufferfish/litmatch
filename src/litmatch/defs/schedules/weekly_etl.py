"""Weekly ETL schedule: runs the ETL pipeline every Sunday at midnight UTC.

This schedule triggers the etl_pipeline job on a weekly basis to keep
the book database fresh with the latest scraped data.

Defaults to STOPPED status so it must be explicitly activated in the
Dagster UI or via configuration.
"""
import dagster as dg

weekly_etl_schedule = dg.ScheduleDefinition(
    name="weekly_etl_schedule",
    job_name="etl_pipeline",
    cron_schedule="0 0 * * 0",
    description="Run the ETL pipeline every Sunday at midnight UTC.",
    default_status=dg.DefaultScheduleStatus.STOPPED,
    execution_timezone="UTC",
)
