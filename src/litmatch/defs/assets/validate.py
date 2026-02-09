"""Validate asset: validates raw book records and splits into valid/invalid.

Produces two outputs:
- validated_books: records that passed validation
- validation_errors: records that failed with their error messages

Yields Output objects with metadata for observability.
"""
import json
import os
from collections.abc import Generator
from datetime import datetime, timezone

import dagster as dg

from litmatch.defs.resources.path import PathResource
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
    path: PathResource,
) -> Generator[dg.Output, None, None]:
    """Validate raw book records, separating valid from invalid.

    Book-level validation checks required fields.
    Review-level validation checks rating values and review text.
    Invalid reviews are filtered out but do not invalidate the book.

    Yields Output objects with metadata for observability.
    """
    valid_books: list[dict] = []
    errors: list[dict] = []
    filtered_reviews_count = 0

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
                filtered_reviews_count += 1

        valid_books.append({**record, "reviews": valid_reviews})

    total = len(raw_books)
    validation_rate = (len(valid_books) / total * 100.0) if total > 0 else 0.0

    context.log.info(
        f"Validation complete: {len(valid_books)} valid, {len(errors)} invalid"
    )

    # Write quarantine file if there are errors
    quarantine_file_path = _write_quarantine_file(errors, path, context)

    yield dg.Output(
        valid_books,
        output_name="validated_books",
        metadata={
            "valid_count": len(valid_books),
            "total_input_count": total,
            "validation_rate": validation_rate,
            "filtered_reviews_count": filtered_reviews_count,
        },
    )

    errors_metadata: dict = {"error_count": len(errors)}
    if quarantine_file_path:
        errors_metadata["quarantine_file"] = quarantine_file_path

    yield dg.Output(
        errors,
        output_name="validation_errors",
        metadata=errors_metadata,
    )


def _write_quarantine_file(
    errors: list[dict], path: PathResource, context: dg.AssetExecutionContext
) -> str | None:
    """Write validation errors to a timestamped JSONL quarantine file.

    Quarantine file writing is a secondary observability concern. If the
    write fails (permissions, disk full, read-only filesystem), the error
    is logged but the asset continues with None returned.

    Args:
        errors: List of error records to quarantine.
        path: PathResource providing the quarantine directory.
        context: Dagster execution context for logging.

    Returns:
        The path to the quarantine file, or None if no errors to write
        or if writing failed.
    """
    if not errors:
        return None

    quarantine_dir = path.quarantine_dir
    try:
        os.makedirs(quarantine_dir, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        filename = f"quarantine_{timestamp}.jsonl"
        filepath = os.path.join(quarantine_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            for error_record in errors:
                f.write(json.dumps(error_record) + "\n")

        context.log.info(
            f"Wrote {len(errors)} error records to quarantine: {filepath}"
        )
        return filepath
    except OSError as err:
        # Log but don't fail -- quarantine is observability, not critical path
        context.log.warning(
            f"Failed to write quarantine file to {quarantine_dir}: {err}"
        )
        return None
