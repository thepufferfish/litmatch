"""Data transformation utilities for the ETL pipeline.

Pure functions that transform raw scraped data into cleaned, normalized forms.
All functions are immutable -- they return new values without modifying inputs.
"""
import re
from datetime import date, datetime

# Known bad years found in real scraped data and their corrections
_BAD_YEAR_REPLACEMENTS: dict[str, str] = {
    "0209": "2019",
    "0000": "2019",
    "-0001": "2019",
}

# Rating string to numeric encoding
_RATING_MAP: dict[str, int] = {
    "Rave": 4,
    "Positive": 3,
    "Mixed": 2,
    "Pan": 1,
}


def fix_publish_date(date_str: str | None) -> date | None:
    """Fix known bad years and parse a publish date string.

    Args:
        date_str: Date string in "Month Day, Year" format, or None/empty.

    Returns:
        Parsed date, or None if unparseable or empty.
    """
    if not date_str:
        return None

    fixed = date_str
    for bad, good in _BAD_YEAR_REPLACEMENTS.items():
        fixed = fixed.replace(bad, good)

    try:
        return datetime.strptime(fixed, "%B %d, %Y").date()
    except ValueError:
        return None


def encode_rating(rating: str) -> int:
    """Encode a textual review rating to a numeric value.

    Args:
        rating: One of 'Rave', 'Positive', 'Mixed', 'Pan'.

    Returns:
        Integer 1-4.

    Raises:
        ValueError: If rating is not a recognized value.
    """
    if rating not in _RATING_MAP:
        raise ValueError(f"Error encoding review rating: unknown rating {rating!r}")
    return _RATING_MAP[rating]


def clean_critic_name(critic: str, publication: str) -> str:
    """Clean a critic name by stripping trailing commas and handling empty values.

    In the real data, ~75% of critic names have a trailing comma.
    Empty critic names fall back to the publication name, then to 'Unknown'.

    Args:
        critic: Raw critic name from JSONL.
        publication: Publication name as fallback.

    Returns:
        Cleaned critic name string.
    """
    cleaned = re.sub(r",\s*$", "", critic).strip()
    if not cleaned:
        cleaned = publication.strip() if publication and publication.strip() else "Unknown"
    return cleaned


def classify_fiction(genres: list[str]) -> bool | None:
    """Classify whether a book is fiction based on its genre list.

    Args:
        genres: List of genre name strings.

    Returns:
        True if 'Fiction' in genres, False if 'Non-Fiction' in genres, None otherwise.
    """
    if "Fiction" in genres:
        return True
    if "Non-Fiction" in genres:
        return False
    return None


def _transform_review(review: dict) -> dict:
    """Transform a single review record.

    Args:
        review: Raw review dict from JSONL.

    Returns:
        New dict with cleaned critic name and encoded rating.
    """
    return {
        **review,
        "critic": clean_critic_name(review["critic"], review["publication"]),
        "rating": encode_rating(review["rating"]),
    }


def transform_book_record(record: dict) -> dict:
    """Apply all data transforms to a raw book record.

    Creates a new dict with:
    - Fixed publish_date (str -> date | None)
    - Parsed last_scraped (str -> datetime)
    - Added is_fiction flag
    - Transformed reviews (cleaned critics, encoded ratings)

    Does NOT mutate the input record.

    Args:
        record: Raw book record dict from JSONL.

    Returns:
        New dict with all transforms applied.
    """
    return {
        **record,
        "publish_date": fix_publish_date(record.get("publish_date")),
        "last_scraped": datetime.fromisoformat(record["last_scraped"]),
        "is_fiction": classify_fiction(record.get("genres", [])),
        "reviews": [_transform_review(r) for r in record.get("reviews", [])],
    }
