"""Input validation for raw JSONL book records.

Validates records before they enter the transform/load pipeline.
Returns (is_valid, errors) tuples to allow the caller to decide
whether to skip or abort.
"""

# Valid rating values from the real data
_VALID_RATINGS = frozenset({"Rave", "Positive", "Mixed", "Pan"})

# Required non-empty string fields on a book record
_REQUIRED_BOOK_FIELDS = ("title", "url", "author", "last_scraped")

# Required non-empty string fields on a review (excluding url -- 68 reviews lack it)
_REQUIRED_REVIEW_FIELDS = ("review",)


def validate_book_record(record: dict) -> tuple[bool, list[str]]:
    """Validate a raw book record from JSONL.

    Required non-empty fields: title, url, author, last_scraped.
    Optional/empty-allowed: description, publisher, publish_date, genres, cover, reviews.

    Args:
        record: Raw dict from parsed JSONL line.

    Returns:
        Tuple of (is_valid, list_of_error_messages).
    """
    errors: list[str] = []

    for field in _REQUIRED_BOOK_FIELDS:
        value = record.get(field)
        if not value or (isinstance(value, str) and not value.strip()):
            errors.append(f"Missing or empty required field: {field}")

    return (len(errors) == 0, errors)


def validate_review(review: dict) -> tuple[bool, list[str]]:
    """Validate a single review dict from a book record.

    Required: rating (must be one of Rave/Positive/Mixed/Pan), review (text).
    Optional/empty-allowed: critic, publication, url (spec deviation: 68 have empty URLs).

    Args:
        review: Raw review dict from JSONL.

    Returns:
        Tuple of (is_valid, list_of_error_messages).
    """
    errors: list[str] = []

    # Check required fields exist
    for field in _REQUIRED_REVIEW_FIELDS:
        value = review.get(field)
        if not value or (isinstance(value, str) and not value.strip()):
            errors.append(f"Missing or empty required field: {field}")

    # Validate rating value
    rating = review.get("rating", "")
    if rating not in _VALID_RATINGS:
        errors.append(
            f"Invalid rating value: {rating!r}. Must be one of {sorted(_VALID_RATINGS)}"
        )

    return (len(errors) == 0, errors)
