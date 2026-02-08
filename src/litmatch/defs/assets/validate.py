"""Validate asset: validates raw book records and splits into valid/invalid.

Produces two outputs:
- validated_books: records that passed validation
- validation_errors: records that failed with their error messages
"""
import dagster as dg

from litmatch.defs.utils.validation import validate_book_record, validate_review


@dg.multi_asset(
    outs={
        "validated_books": dg.AssetOut(
            description="Book records that passed validation",
            kinds={"python"},
        ),
        "validation_errors": dg.AssetOut(
            description="Book records that failed validation, with error details",
            kinds={"python"},
        ),
    },
)
def validate_raw_books(
    context: dg.AssetExecutionContext,
    raw_books: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Validate raw book records, separating valid from invalid.

    Book-level validation checks required fields.
    Review-level validation checks rating values and review text.
    Invalid reviews are filtered out but do not invalidate the book.
    """
    valid_books: list[dict] = []
    errors: list[dict] = []

    for record in raw_books:
        is_valid, book_errors = validate_book_record(record)

        if not is_valid:
            errors.append({
                "url": record.get("url", "unknown"),
                "title": record.get("title", "unknown"),
                "errors": book_errors,
            })
            continue

        # Filter out invalid reviews but keep the book
        valid_reviews: list[dict] = []
        for review in record.get("reviews", []):
            review_valid, review_errors = validate_review(review)
            if review_valid:
                valid_reviews.append(review)
            else:
                context.log.warning(
                    f"Skipping invalid review for {record.get('title', 'unknown')}: "
                    f"{review_errors}"
                )

        valid_books.append({**record, "reviews": valid_reviews})

    context.log.info(
        f"Validation complete: {len(valid_books)} valid, {len(errors)} invalid"
    )
    return valid_books, errors
