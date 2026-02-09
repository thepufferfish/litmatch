import os

import dagster as dg

from litmatch.defs.assets.crawl import crawl_books
from litmatch.defs.assets.extract import raw_books
from litmatch.defs.assets.load import load_books
from litmatch.defs.assets.transform import cleaned_books
from litmatch.defs.assets.validate import validate_raw_books
from litmatch.defs.jobs import crawl_and_load, etl_pipeline
from litmatch.defs.resources.database import DatabaseResource
from litmatch.defs.resources.path import PathResource
from litmatch.defs.resources.scrapyd import ScrapydResource
from litmatch.defs.schedules import weekly_etl_schedule
from litmatch.defs.sensors.data_freshness import data_freshness_sensor
from litmatch.defs.sensors.startup_crawl import startup_crawl_sensor


def _get_database_url() -> str:
    """Read DATABASE_URL from environment, failing fast if absent.

    Raises:
        EnvironmentError: If DATABASE_URL is not set.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise EnvironmentError(
            "DATABASE_URL environment variable is required but not set. "
            "Set it to a PostgreSQL connection string, e.g. "
            "postgresql://user:pass@host:5432/dbname"
        )
    return url


def _get_raw_data_dir() -> str:
    """Read RAW_DATA_DIR from environment with a safe default."""
    return os.environ.get("RAW_DATA_DIR", "scraper/output/raw")


def _get_scrapyd_url() -> str:
    """Read SCRAPYD_URL from environment with a safe default."""
    return os.environ.get("SCRAPYD_URL", "http://localhost:6800")


@dg.definitions
def defs():
    return dg.Definitions(
        assets=[crawl_books, raw_books, validate_raw_books, cleaned_books, load_books],
        jobs=[etl_pipeline, crawl_and_load],
        schedules=[weekly_etl_schedule],
        sensors=[data_freshness_sensor, startup_crawl_sensor],
        resources={
            "database": DatabaseResource(connection_string=_get_database_url()),
            "path": PathResource(raw_data_dir=_get_raw_data_dir()),
            "scrapyd": ScrapydResource(base_url=_get_scrapyd_url()),
        },
    )
