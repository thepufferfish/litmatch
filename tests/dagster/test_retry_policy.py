"""Tests for Phase 2: Retry policy on load_books asset.

load_books should have a RetryPolicy with max_retries=2 and exponential backoff
to handle transient database failures gracefully.

TDD Phase: RED -- these tests should fail before implementation.
"""
import dagster as dg
import pytest


class TestLoadBooksRetryPolicy:
    """load_books asset should have a retry policy configured."""

    def test_has_retry_policy(self) -> None:
        """load_books should have a RetryPolicy attached."""
        from litmatch.defs.assets.load import load_books

        retry_policy = load_books.op.retry_policy
        assert retry_policy is not None

    def test_max_retries_is_two(self) -> None:
        """The retry policy should allow a maximum of 2 retries."""
        from litmatch.defs.assets.load import load_books

        retry_policy = load_books.op.retry_policy
        assert retry_policy is not None
        assert retry_policy.max_retries == 2

    def test_uses_exponential_backoff(self) -> None:
        """The retry policy should use exponential backoff strategy."""
        from litmatch.defs.assets.load import load_books

        retry_policy = load_books.op.retry_policy
        assert retry_policy is not None
        assert retry_policy.backoff == dg.Backoff.EXPONENTIAL

    def test_has_delay(self) -> None:
        """The retry policy should have a base delay configured."""
        from litmatch.defs.assets.load import load_books

        retry_policy = load_books.op.retry_policy
        assert retry_policy is not None
        assert retry_policy.delay > 0

    def test_other_assets_have_no_retry_policy(self) -> None:
        """Only load_books should have a retry policy; other assets should not."""
        from litmatch.defs.assets.crawl import crawl_books
        from litmatch.defs.assets.extract import raw_books
        from litmatch.defs.assets.transform import cleaned_books

        for asset in [raw_books, crawl_books, cleaned_books]:
            assert asset.op.retry_policy is None, (
                f"Asset {asset.op.name} should not have a retry policy"
            )
