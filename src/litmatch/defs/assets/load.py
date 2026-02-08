"""Load asset: upserts transformed book records into PostgreSQL.

This is the final asset in the pipeline. It takes cleaned/transformed
records and upserts them into the database using SQLModel.
"""
import dagster as dg
from sqlmodel import Session

from litmatch.defs.resources.database import DatabaseResource
from litmatch.defs.utils.db_operations import upsert_book


@dg.asset(
    description="Load cleaned book records into PostgreSQL",
    kinds={"python", "postgres"},
)
def load_books(
    context: dg.AssetExecutionContext,
    database: DatabaseResource,
    cleaned_books: list[dict],
) -> None:
    """Upsert cleaned book records into the database.

    For each record:
    - If the book URL doesn't exist, insert it
    - If it exists and the scrape is newer, update it
    - If it exists and the scrape is older, skip it

    Creates associated authors, publishers, genres, critics,
    publications, and reviews as needed.
    """
    engine = database.get_engine()
    inserted = 0
    skipped = 0

    context.log.info(f"Loading {len(cleaned_books)} records into database")

    with Session(engine) as session:
        for record in cleaned_books:
            try:
                was_upserted = upsert_book(session, record)
                if was_upserted:
                    inserted += 1
                else:
                    skipped += 1
            except Exception as err:
                context.log.error(
                    f"Error loading {record.get('title', 'unknown')}: {err}"
                )
                session.rollback()
                continue

        session.commit()

    context.log.info(
        f"Load complete: {inserted} inserted/updated, {skipped} skipped"
    )
