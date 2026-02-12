"""Staging table operations for reading raw scraped data.

Provides functions to query the raw_books_staging table that the
Scrapy pipeline writes to during crawls.
"""
from dataclasses import dataclass

from sqlalchemy import Engine, text


@dataclass(frozen=True)
class StagingDataState:
    """Current state of staging table data.

    Attributes:
        crawl_job_id: The latest crawl job ID in the staging table.
        max_id: The maximum row ID for the latest crawl job.
        row_count: Total number of rows for the latest crawl job.
    """
    crawl_job_id: str
    max_id: int
    row_count: int


def ensure_staging_table(engine: Engine) -> None:
    """Create the raw_books_staging table if it does not exist.

    Idempotent operation that creates the table with the same schema
    as the Scrapy pipeline uses, plus indexes on crawl_job_id and
    created_at.

    Args:
        engine: SQLAlchemy engine connected to the database.
    """
    with engine.connect() as conn:
        conn.execute(
            text("""
                CREATE TABLE IF NOT EXISTS raw_books_staging (
                    id SERIAL PRIMARY KEY,
                    crawl_job_id VARCHAR(64) NOT NULL,
                    item_data JSONB NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    url TEXT
                )
            """)
        )
        conn.execute(
            text("""
                CREATE INDEX IF NOT EXISTS idx_staging_crawl_job_id
                ON raw_books_staging (crawl_job_id)
            """)
        )
        conn.execute(
            text("""
                CREATE INDEX IF NOT EXISTS idx_staging_created_at
                ON raw_books_staging (created_at)
            """)
        )
        conn.commit()


def get_latest_crawl_job_id(engine: Engine) -> str | None:
    """Get the most recent crawl_job_id from the staging table.

    Args:
        engine: SQLAlchemy engine connected to the database.

    Returns:
        The latest crawl_job_id, or None if the table is empty.
    """
    with engine.connect() as conn:
        row = conn.execute(
            text("""
                SELECT crawl_job_id
                FROM raw_books_staging
                ORDER BY created_at DESC
                LIMIT 1
            """)
        ).fetchone()

        if row is None:
            return None
        return row[0]


def fetch_staged_items_by_job_id(engine: Engine, job_id: str) -> list[dict]:
    """Fetch all staged items for a given crawl job ID.

    Args:
        engine: SQLAlchemy engine connected to the database.
        job_id: The crawl job ID to filter by.

    Returns:
        List of dicts (the JSONB item_data values) ordered by row ID.
    """
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT item_data
                FROM raw_books_staging
                WHERE crawl_job_id = :job_id
                ORDER BY id
            """),
            {"job_id": job_id},
        )
        return [row[0] for row in result]


def fetch_latest_staged_items(engine: Engine) -> tuple[str, list[dict]]:
    """Fetch all staged items from the most recent crawl.

    Uses a single connection to avoid a race condition where another
    process could delete the rows between finding the job ID and
    fetching the items.

    Args:
        engine: SQLAlchemy engine connected to the database.

    Returns:
        Tuple of (crawl_job_id, items). Returns ("", []) if the
        staging table is empty.
    """
    with engine.connect() as conn:
        latest = conn.execute(
            text("""
                SELECT crawl_job_id
                FROM raw_books_staging
                ORDER BY created_at DESC
                LIMIT 1
            """)
        ).fetchone()

        if latest is None:
            return ("", [])

        job_id = latest[0]

        result = conn.execute(
            text("""
                SELECT item_data
                FROM raw_books_staging
                WHERE crawl_job_id = :job_id
                ORDER BY id
            """),
            {"job_id": job_id},
        )
        items = [row[0] for row in result]

    return (job_id, items)


def cleanup_old_staging_data(engine: Engine, retention_days: int = 30) -> int:
    """Delete staging rows older than the retention period.

    Args:
        engine: SQLAlchemy engine connected to the database.
        retention_days: Number of days to retain data. Rows with
            created_at older than this many days ago are deleted.

    Returns:
        Number of rows deleted.
    """
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                DELETE FROM raw_books_staging
                WHERE created_at < NOW() - make_interval(days => :days)
            """),
            {"days": retention_days},
        )
        deleted = result.rowcount
        conn.commit()
        return deleted


def get_staging_data_state(engine: Engine) -> StagingDataState | None:
    """Get current state of staging table data.

    Returns the latest crawl_job_id, the maximum row ID for that job,
    and the total row count for that job. This enables incremental
    processing by tracking which rows have been processed.

    Args:
        engine: SQLAlchemy engine connected to the database.

    Returns:
        StagingDataState with job_id, max_id, and row_count, or None
        if the staging table is empty.
    """
    with engine.connect() as conn:
        # Get the latest crawl_job_id and its max ID and count in one query
        row = conn.execute(
            text("""
                SELECT crawl_job_id, MAX(id) as max_id, COUNT(*) as row_count
                FROM raw_books_staging
                WHERE crawl_job_id = (
                    SELECT crawl_job_id
                    FROM raw_books_staging
                    ORDER BY created_at DESC
                    LIMIT 1
                )
                GROUP BY crawl_job_id
            """)
        ).fetchone()

        if row is None:
            return None

        return StagingDataState(
            crawl_job_id=row[0],
            max_id=row[1],
            row_count=row[2],
        )


def fetch_staged_items_since_id(
    engine: Engine,
    crawl_job_id: str,
    after_id: int = 0,
) -> list[dict]:
    """Fetch staged items with row ID greater than after_id.

    Enables incremental extraction of staging data by fetching only
    rows that have not been processed yet (id > after_id).

    Args:
        engine: SQLAlchemy engine connected to the database.
        crawl_job_id: The crawl job ID to filter by.
        after_id: Only fetch rows with id > this value. Defaults to 0
            (fetch all rows for the job).

    Returns:
        List of dicts (JSONB item_data values) ordered by row ID.
    """
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT item_data
                FROM raw_books_staging
                WHERE crawl_job_id = :job_id
                  AND id > :after_id
                ORDER BY id
            """),
            {"job_id": crawl_job_id, "after_id": after_id},
        )
        return [row[0] for row in result]
