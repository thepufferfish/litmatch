"""Shared test fixtures for Dagster pipeline tests.

Fixtures are modeled after real JSONL data from scraper/output/raw/books.jsonl.
"""
import json
import os
import tempfile

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


@pytest.fixture
def sample_book_record() -> dict:
    """A complete, valid book record matching real JSONL shape."""
    return {
        "title": "Death and the Gardener",
        "author": "Georgi Gospodinov",
        "publisher": "Liveright",
        "publish_date": "October 7, 2025",
        "description": "A novel about a father, a son, and the botany of grief.",
        "genres": ["Fiction", "Literary", "Literature in Translation"],
        "url": "https://bookmarks.reviews/reviews/death-and-the-gardener/",
        "cover": "https://s26162.pcdn.co/wp-content/uploads/sites/2/2025/10/cover.gif",
        "last_scraped": "2025-10-13 11:23:31",
        "reviews": [
            {
                "critic": "Toby Lichtig,",
                "publication": "",
                "rating": "Rave",
                "review": "Profoundly moving ... Excellent.",
                "url": "",
            },
            {
                "critic": "Alexandra Jacobs,",
                "publication": "The New York Times",
                "rating": "Positive",
                "review": "Its 200-odd pages have a stop-and-start quality.",
                "url": "https://www.nytimes.com/2025/10/05/books/review/death.html",
            },
        ],
    }


@pytest.fixture
def sample_nonfiction_record() -> dict:
    """A non-fiction book record."""
    return {
        "title": "Girl on Girl",
        "author": "Sophie Gilbert",
        "publisher": "Penguin Press",
        "publish_date": "April 29, 2025",
        "description": "What happened to feminism in the twenty-first century?",
        "genres": ["Culture", "History", "Non-Fiction", "Social Sciences"],
        "url": "https://bookmarks.reviews/reviews/girl-on-girl/",
        "cover": "https://s26162.pcdn.co/wp-content/uploads/sites/2/2025/04/cover.gif",
        "last_scraped": "2025-10-13 11:23:32",
        "reviews": [
            {
                "critic": "",
                "publication": "Kirkus",
                "rating": "Rave",
                "review": "A carefully buttressed analysis.",
                "url": "https://www.kirkusreviews.com/book-reviews/girl-on-girl/",
            },
            {
                "critic": "Kate Womersley,",
                "publication": "The Guardian (UK)",
                "rating": "Mixed",
                "review": "Skilful marshalling of evidence.",
                "url": "https://www.theguardian.com/books/2025/girl-on-girl/",
            },
        ],
    }


@pytest.fixture
def record_with_bad_date() -> dict:
    """A record with a known bad publish date (0209 -> 2019)."""
    return {
        "title": "Bad Date Book",
        "author": "Test Author",
        "publisher": "Test Publisher",
        "publish_date": "January 1, 0209",
        "description": "A book with a bad date.",
        "genres": ["Fiction"],
        "url": "https://bookmarks.reviews/reviews/bad-date-book/",
        "cover": None,
        "last_scraped": "2025-01-01 00:00:00",
        "reviews": [],
    }


@pytest.fixture
def record_with_empty_description() -> dict:
    """A record with an empty description (6 exist in real data)."""
    return {
        "title": "No Description Book",
        "author": "Test Author",
        "publisher": "Test Publisher",
        "publish_date": "March 15, 2024",
        "description": "",
        "genres": ["Non-Fiction"],
        "url": "https://bookmarks.reviews/reviews/no-description/",
        "cover": None,
        "last_scraped": "2025-01-01 00:00:00",
        "reviews": [],
    }


@pytest.fixture
def sample_records(
    sample_book_record: dict,
    sample_nonfiction_record: dict,
) -> list[dict]:
    """A list of sample records for batch processing tests."""
    return [sample_book_record, sample_nonfiction_record]


@pytest.fixture
def jsonl_file(sample_records: list[dict], tmp_path) -> str:
    """Write sample records to a temporary JSONL file and return the path."""
    filepath = tmp_path / "books.jsonl"
    with open(filepath, "w", encoding="utf-8") as f:
        for record in sample_records:
            f.write(json.dumps(record) + "\n")
    return str(filepath)


@pytest.fixture
def jsonl_file_with_bad_line(sample_book_record: dict, tmp_path) -> str:
    """A JSONL file containing one valid and one malformed line."""
    filepath = tmp_path / "books_bad.jsonl"
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(json.dumps(sample_book_record) + "\n")
        f.write("this is not valid json\n")
        f.write(json.dumps(sample_book_record) + "\n")
    return str(filepath)


@pytest.fixture(scope="function")
def test_db_engine() -> Engine:
    """Provide an in-memory SQLite database engine for testing.

    Each test function gets a fresh database instance.
    """
    engine = create_engine("sqlite:///:memory:")
    yield engine
    engine.dispose()
