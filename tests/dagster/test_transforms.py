"""Tests for data transformation utilities.

Covers: date fixing, rating encoding, critic name cleaning, fiction classification.
"""
import pytest
from datetime import date


class TestFixPublishDate:
    """Tests for fix_publish_date: str -> date | None."""

    def test_valid_date(self) -> None:
        from litmatch.defs.utils.transforms import fix_publish_date

        result = fix_publish_date("October 7, 2025")
        assert result == date(2025, 10, 7)

    def test_bad_year_0209(self) -> None:
        from litmatch.defs.utils.transforms import fix_publish_date

        result = fix_publish_date("January 1, 0209")
        assert result == date(2019, 1, 1)

    def test_bad_year_0000(self) -> None:
        from litmatch.defs.utils.transforms import fix_publish_date

        result = fix_publish_date("March 15, 0000")
        assert result is not None
        assert result.year == 2019

    def test_bad_year_negative(self) -> None:
        from litmatch.defs.utils.transforms import fix_publish_date

        result = fix_publish_date("June 1, -0001")
        assert result is not None
        assert result.year == 2019

    def test_empty_string_returns_none(self) -> None:
        from litmatch.defs.utils.transforms import fix_publish_date

        assert fix_publish_date("") is None

    def test_none_returns_none(self) -> None:
        from litmatch.defs.utils.transforms import fix_publish_date

        assert fix_publish_date(None) is None

    def test_unparseable_returns_none(self) -> None:
        from litmatch.defs.utils.transforms import fix_publish_date

        assert fix_publish_date("not a date") is None

    def test_different_format_returns_none(self) -> None:
        from litmatch.defs.utils.transforms import fix_publish_date

        assert fix_publish_date("2025-10-07") is None


class TestEncodeRating:
    """Tests for encode_rating: str -> int."""

    def test_rave(self) -> None:
        from litmatch.defs.utils.transforms import encode_rating

        assert encode_rating("Rave") == 4

    def test_positive(self) -> None:
        from litmatch.defs.utils.transforms import encode_rating

        assert encode_rating("Positive") == 3

    def test_mixed(self) -> None:
        from litmatch.defs.utils.transforms import encode_rating

        assert encode_rating("Mixed") == 2

    def test_pan(self) -> None:
        from litmatch.defs.utils.transforms import encode_rating

        assert encode_rating("Pan") == 1

    def test_unknown_raises_value_error(self) -> None:
        from litmatch.defs.utils.transforms import encode_rating

        with pytest.raises(ValueError, match="unknown rating"):
            encode_rating("Unknown")

    def test_empty_raises_value_error(self) -> None:
        from litmatch.defs.utils.transforms import encode_rating

        with pytest.raises(ValueError, match="unknown rating"):
            encode_rating("")

    def test_case_sensitive(self) -> None:
        from litmatch.defs.utils.transforms import encode_rating

        with pytest.raises(ValueError, match="unknown rating"):
            encode_rating("rave")


class TestCleanCriticName:
    """Tests for clean_critic_name: str -> str.

    Real data has trailing commas on ~75% of critic names.
    Empty critic names should fall back to publication or 'Unknown'.
    """

    def test_strips_trailing_comma(self) -> None:
        from litmatch.defs.utils.transforms import clean_critic_name

        assert clean_critic_name("Toby Lichtig,", "") == "Toby Lichtig"

    def test_strips_trailing_comma_with_space(self) -> None:
        from litmatch.defs.utils.transforms import clean_critic_name

        assert clean_critic_name("Toby Lichtig, ", "") == "Toby Lichtig"

    def test_empty_critic_falls_back_to_publication(self) -> None:
        from litmatch.defs.utils.transforms import clean_critic_name

        assert clean_critic_name("", "Kirkus") == "Kirkus"

    def test_empty_critic_empty_publication_returns_unknown(self) -> None:
        from litmatch.defs.utils.transforms import clean_critic_name

        assert clean_critic_name("", "") == "Unknown"

    def test_normal_name_unchanged(self) -> None:
        from litmatch.defs.utils.transforms import clean_critic_name

        assert clean_critic_name("John Self", "") == "John Self"

    def test_whitespace_only_critic_falls_back(self) -> None:
        from litmatch.defs.utils.transforms import clean_critic_name

        assert clean_critic_name("  ", "Kirkus") == "Kirkus"


class TestClassifyFiction:
    """Tests for classify_fiction: list[str] -> bool | None."""

    def test_fiction_genre(self) -> None:
        from litmatch.defs.utils.transforms import classify_fiction

        assert classify_fiction(["Fiction", "Literary"]) is True

    def test_nonfiction_genre(self) -> None:
        from litmatch.defs.utils.transforms import classify_fiction

        assert classify_fiction(["Culture", "Non-Fiction"]) is False

    def test_both_fiction_and_nonfiction_prefers_fiction(self) -> None:
        from litmatch.defs.utils.transforms import classify_fiction

        # Fiction check comes first
        assert classify_fiction(["Fiction", "Non-Fiction"]) is True

    def test_neither_returns_none(self) -> None:
        from litmatch.defs.utils.transforms import classify_fiction

        assert classify_fiction(["Poetry", "Literary"]) is None

    def test_empty_list_returns_none(self) -> None:
        from litmatch.defs.utils.transforms import classify_fiction

        assert classify_fiction([]) is None


class TestTransformBookRecord:
    """Tests for transform_book_record: applies all transforms to a raw record."""

    def test_transforms_complete_record(self, sample_book_record: dict) -> None:
        from litmatch.defs.utils.transforms import transform_book_record

        result = transform_book_record(sample_book_record)

        # Should not mutate original
        assert sample_book_record["publish_date"] == "October 7, 2025"

        assert result["title"] == "Death and the Gardener"
        assert result["publish_date"] == date(2025, 10, 7)
        assert result["is_fiction"] is True
        assert result["last_scraped"] is not None
        # Reviews should have cleaned critic names and encoded ratings
        assert result["reviews"][0]["critic"] == "Toby Lichtig"
        assert result["reviews"][0]["rating"] == 4  # Rave -> 4
        assert result["reviews"][1]["critic"] == "Alexandra Jacobs"
        assert result["reviews"][1]["rating"] == 3  # Positive -> 3

    def test_transforms_nonfiction_record(self, sample_nonfiction_record: dict) -> None:
        from litmatch.defs.utils.transforms import transform_book_record

        result = transform_book_record(sample_nonfiction_record)

        assert result["is_fiction"] is False
        # Empty critic falls back to publication
        assert result["reviews"][0]["critic"] == "Kirkus"

    def test_transforms_bad_date_record(self, record_with_bad_date: dict) -> None:
        from litmatch.defs.utils.transforms import transform_book_record

        result = transform_book_record(record_with_bad_date)

        assert result["publish_date"] == date(2019, 1, 1)

    def test_does_not_mutate_input(self, sample_book_record: dict) -> None:
        from litmatch.defs.utils.transforms import transform_book_record

        original_title = sample_book_record["title"]
        original_date = sample_book_record["publish_date"]
        original_reviews = sample_book_record["reviews"][0]["critic"]

        transform_book_record(sample_book_record)

        assert sample_book_record["title"] == original_title
        assert sample_book_record["publish_date"] == original_date
        assert sample_book_record["reviews"][0]["critic"] == original_reviews
