"""Transform asset: applies data transformations to validated book records.

Transforms include:
- Fix publish dates (str -> date)
- Parse last_scraped (str -> datetime)
- Encode ratings (str -> int)
- Clean critic names (strip trailing commas, handle empties)
- Classify fiction/non-fiction
"""
import dagster as dg

from litmatch.defs.utils.transforms import transform_book_record


@dg.asset(
    description="Cleaned and transformed book records ready for loading",
    kinds={"python"},
)
def cleaned_books(
    context: dg.AssetExecutionContext,
    validated_books: list[dict],
) -> dg.Output[list[dict]]:
    """Apply all data transforms to validated book records.

    Each record gets:
    - publish_date: str -> date | None
    - last_scraped: str -> datetime
    - is_fiction: bool | None (derived from genres)
    - reviews[].rating: str -> int
    - reviews[].critic: cleaned name string
    """
    transformed: list[dict] = []
    skipped = 0

    for record in validated_books:
        try:
            transformed.append(transform_book_record(record))
        except (ValueError, KeyError) as err:
            context.log.warning(
                f"Skipping record {record.get('title', 'unknown')} "
                f"due to transform error: {err}"
            )
            skipped += 1

    context.log.info(
        f"Transformed {len(transformed)} records ({skipped} skipped)"
    )
    return dg.Output(
        transformed,
        metadata={
            "transformed_count": len(transformed),
            "skipped_count": skipped,
        },
    )
