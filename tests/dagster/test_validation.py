"""Tests for input validation utilities.

Validates raw JSONL book records before processing.
"""
import pytest


class TestValidateBookRecord:
    """Tests for validate_book_record: dict -> tuple[bool, list[str]]."""

    def test_valid_record_passes(self, sample_book_record: dict) -> None:
        from litmatch.defs.utils.validation import validate_book_record

        is_valid, errors = validate_book_record(sample_book_record)
        assert is_valid is True
        assert errors == []

    def test_missing_title_fails(self, sample_book_record: dict) -> None:
        from litmatch.defs.utils.validation import validate_book_record

        record = {**sample_book_record, "title": ""}
        is_valid, errors = validate_book_record(record)
        assert is_valid is False
        assert any("title" in e for e in errors)

    def test_missing_url_fails(self, sample_book_record: dict) -> None:
        from litmatch.defs.utils.validation import validate_book_record

        record = {**sample_book_record, "url": ""}
        is_valid, errors = validate_book_record(record)
        assert is_valid is False
        assert any("url" in e for e in errors)

    def test_missing_author_fails(self, sample_book_record: dict) -> None:
        from litmatch.defs.utils.validation import validate_book_record

        record = {**sample_book_record, "author": ""}
        is_valid, errors = validate_book_record(record)
        assert is_valid is False
        assert any("author" in e for e in errors)

    def test_missing_last_scraped_fails(self, sample_book_record: dict) -> None:
        from litmatch.defs.utils.validation import validate_book_record

        record = {**sample_book_record, "last_scraped": ""}
        is_valid, errors = validate_book_record(record)
        assert is_valid is False
        assert any("last_scraped" in e for e in errors)

    def test_missing_key_entirely_fails(self) -> None:
        from litmatch.defs.utils.validation import validate_book_record

        record = {"title": "Test"}  # Missing most required fields
        is_valid, errors = validate_book_record(record)
        assert is_valid is False
        assert len(errors) >= 3  # url, author, last_scraped at minimum

    def test_empty_description_still_valid(self, sample_book_record: dict) -> None:
        """6 books in real data have empty descriptions -- this is allowed."""
        from litmatch.defs.utils.validation import validate_book_record

        record = {**sample_book_record, "description": ""}
        is_valid, errors = validate_book_record(record)
        assert is_valid is True

    def test_missing_genres_still_valid(self, sample_book_record: dict) -> None:
        """Genres can be empty -- book just won't be classified."""
        from litmatch.defs.utils.validation import validate_book_record

        record = {**sample_book_record, "genres": []}
        is_valid, errors = validate_book_record(record)
        assert is_valid is True

    def test_none_cover_still_valid(self, sample_book_record: dict) -> None:
        from litmatch.defs.utils.validation import validate_book_record

        record = {**sample_book_record, "cover": None}
        is_valid, errors = validate_book_record(record)
        assert is_valid is True

    def test_collects_multiple_errors(self) -> None:
        from litmatch.defs.utils.validation import validate_book_record

        record = {
            "title": "",
            "author": "",
            "publisher": "",
            "publish_date": "",
            "description": "",
            "genres": [],
            "url": "",
            "cover": None,
            "last_scraped": "",
            "reviews": [],
        }
        is_valid, errors = validate_book_record(record)
        assert is_valid is False
        # title, url, author, last_scraped are all required
        assert len(errors) >= 4


class TestValidateReview:
    """Tests for validate_review: dict -> tuple[bool, list[str]]."""

    def test_valid_review_passes(self) -> None:
        from litmatch.defs.utils.validation import validate_review

        review = {
            "critic": "John Self,",
            "publication": "Financial Times",
            "rating": "Rave",
            "review": "A great book.",
            "url": "https://example.com/review",
        }
        is_valid, errors = validate_review(review)
        assert is_valid is True

    def test_invalid_rating_fails(self) -> None:
        from litmatch.defs.utils.validation import validate_review

        review = {
            "critic": "John Self",
            "publication": "FT",
            "rating": "Excellent",
            "review": "Good.",
            "url": "https://example.com/review",
        }
        is_valid, errors = validate_review(review)
        assert is_valid is False
        assert any("rating" in e for e in errors)

    def test_empty_rating_fails(self) -> None:
        from litmatch.defs.utils.validation import validate_review

        review = {
            "critic": "John Self",
            "publication": "FT",
            "rating": "",
            "review": "Good.",
            "url": "",
        }
        is_valid, errors = validate_review(review)
        assert is_valid is False

    def test_empty_review_text_fails(self) -> None:
        from litmatch.defs.utils.validation import validate_review

        review = {
            "critic": "John Self",
            "publication": "FT",
            "rating": "Rave",
            "review": "",
            "url": "https://example.com",
        }
        is_valid, errors = validate_review(review)
        assert is_valid is False
        assert any("review" in e.lower() for e in errors)

    def test_empty_url_still_valid(self) -> None:
        """68 reviews in real data have empty URLs -- this is allowed (spec deviation)."""
        from litmatch.defs.utils.validation import validate_review

        review = {
            "critic": "John Self",
            "publication": "FT",
            "rating": "Rave",
            "review": "Good book.",
            "url": "",
        }
        is_valid, errors = validate_review(review)
        assert is_valid is True

    def test_empty_critic_and_publication_still_valid(self) -> None:
        """Both can be empty; transform will set critic to 'Unknown'."""
        from litmatch.defs.utils.validation import validate_review

        review = {
            "critic": "",
            "publication": "",
            "rating": "Mixed",
            "review": "Meh.",
            "url": "",
        }
        is_valid, errors = validate_review(review)
        assert is_valid is True

    def test_missing_key_fails(self) -> None:
        from litmatch.defs.utils.validation import validate_review

        review = {"rating": "Rave"}
        is_valid, errors = validate_review(review)
        assert is_valid is False
