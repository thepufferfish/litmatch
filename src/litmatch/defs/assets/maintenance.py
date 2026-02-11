"""Maintenance assets for database housekeeping.

Provides automated cleanup tasks such as expired refresh token removal
and staging table data cleanup.
"""
from datetime import datetime, timezone

import dagster as dg
from sqlmodel import Session, delete

from backend.db.models import RefreshToken
from litmatch.defs.resources.database import DatabaseResource
from litmatch.defs.utils.staging import cleanup_old_staging_data


@dg.asset(
    description="Delete expired refresh tokens from the database",
    group_name="maintenance",
    kinds={"python", "postgres"},
)
def cleanup_expired_tokens(
    context: dg.AssetExecutionContext,
    database: DatabaseResource,
) -> dg.MaterializeResult:
    """Delete all refresh tokens whose expires_at is in the past.

    Returns:
        MaterializeResult with metadata about the number of deleted tokens.
    """
    engine = database.get_engine()
    cutoff = datetime.now(timezone.utc)

    with Session(engine) as session:
        stmt = delete(RefreshToken).where(RefreshToken.expires_at < cutoff)
        result = session.execute(stmt)
        deleted_count = result.rowcount
        session.commit()

    context.log.info(f"Deleted {deleted_count} expired refresh tokens")

    return dg.MaterializeResult(
        metadata={
            "deleted_count": deleted_count,
        },
    )


@dg.asset(
    deps=["load_books"],
    description="Clean up staging table rows older than retention period",
    group_name="maintenance",
    kinds={"python", "postgres"},
)
def cleanup_staging(
    context: dg.AssetExecutionContext,
    database: DatabaseResource,
) -> dg.MaterializeResult:
    """Delete staging table rows older than the retention period.

    Removes rows from raw_books_staging that are older than 30 days
    to prevent unbounded table growth after ETL loads complete.

    Args:
        context: Dagster asset execution context for logging.
        database: DatabaseResource providing a SQLAlchemy engine.

    Returns:
        MaterializeResult with metadata about the number of deleted rows.
    """
    engine = database.get_engine()
    try:
        rows_deleted = cleanup_old_staging_data(engine, retention_days=30)
        context.log.info(
            f"Deleted {rows_deleted} staging rows older than 30 days"
        )

        return dg.MaterializeResult(
            metadata={
                "rows_deleted": rows_deleted,
            },
        )
    finally:
        engine.dispose()
