"""Load asset: upserts transformed book records into PostgreSQL.

This is the final asset in the pipeline. It takes cleaned/transformed
records and upserts them into the database using SQLModel.

Configured with a RetryPolicy for transient database failures.
"""
import dagster as dg
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from litmatch.defs.resources.database import DatabaseResource
from litmatch.defs.utils.db_operations import upsert_book


@dg.asset(
    description="Load cleaned book records into PostgreSQL",
    kinds={"python", "postgres"},
    retry_policy=dg.RetryPolicy(
        max_retries=2,
        delay=30,
        backoff=dg.Backoff.EXPONENTIAL,
    ),
)
def load_books(
    context: dg.AssetExecutionContext,
    database: DatabaseResource,
    cleaned_books: list[dict],
) -> dg.MaterializeResult:
    """Upsert cleaned book records into the database.

    For each record:
    - If the book URL doesn't exist, insert it
    - If it exists and the scrape is newer, update it
    - If it exists and the scrape is older, skip it

    Creates associated authors, publishers, genres, critics,
    publications, and reviews as needed.

    Returns:
        MaterializeResult with metadata about the load operation.
    """
    engine = database.get_engine()
    inserted = 0
    skipped = 0
    error_count = 0

    context.log.info(f"Loading {len(cleaned_books)} records into database")

    with Session(engine) as session:
        for record in cleaned_books:
            savepoint = session.begin_nested()
            try:
                was_upserted = upsert_book(session, record)
                if was_upserted:
                    inserted += 1
                else:
                    skipped += 1
                savepoint.commit()
            except SQLAlchemyError as err:
                context.log.error(
                    f"Database error loading {record.get('title', 'unknown')}: {err}"
                )
                savepoint.rollback()
                error_count += 1
                continue

        session.commit()

    context.log.info(
        f"Load complete: {inserted} inserted/updated, {skipped} skipped, "
        f"{error_count} errors"
    )

    return dg.MaterializeResult(
        metadata={
            "inserted_count": inserted,
            "skipped_count": skipped,
            "error_count": error_count,
            "total_count": len(cleaned_books),
        },
    )
