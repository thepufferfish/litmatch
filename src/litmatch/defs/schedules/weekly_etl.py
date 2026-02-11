"""Weekly crawl schedule: runs the crawl pipeline every Sunday at midnight UTC.

This schedule triggers the crawl job on a weekly basis to keep
the book database fresh with the latest scraped data.

Defaults to STOPPED status so it must be explicitly activated in the
Dagster UI or via configuration.
"""
import dagster as dg

weekly_crawl_schedule = dg.ScheduleDefinition(
    name="weekly_crawl_schedule",
    job_name="crawl",
    cron_schedule="0 0 * * 0",
    description="Run the scrapy crawl every Sunday at midnight UTC.",
    default_status=dg.DefaultScheduleStatus.STOPPED,
    execution_timezone="UTC",
)
