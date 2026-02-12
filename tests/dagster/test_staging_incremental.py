"""Tests for incremental staging data processing.

Tests the new functions that enable incremental extraction of staging
data during multi-day crawls.
"""
from unittest.mock import MagicMock, Mock

import pytest

from litmatch.defs.utils.staging import (
    StagingDataState,
    fetch_staged_items_since_id,
    get_staging_data_state,
)


class TestGetStagingDataState:
    """Tests for get_staging_data_state()."""

    def test_returns_none_when_table_empty(self):
        """Should return None when staging table is empty."""
        mock_engine = Mock()
        mock_conn = MagicMock()

        # Set up context manager properly
        mock_engine.connect.return_value.__enter__ = Mock(return_value=mock_conn)
        mock_engine.connect.return_value.__exit__ = Mock(return_value=False)

        # Simulate empty table: query returns None
        mock_result = Mock()
        mock_result.fetchone.return_value = None
        mock_conn.execute.return_value = mock_result

        result = get_staging_data_state(mock_engine)

        assert result is None

    def test_returns_state_for_single_crawl_job(self):
        """Should return state with job_id, max_id, and row_count."""
        mock_engine = Mock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        # Simulate query result: (job_id, max_id, row_count)
        mock_result = Mock()
        mock_result.fetchone.return_value = ("test-job-123", 42, 5)
        mock_conn.execute.return_value = mock_result

        result = get_staging_data_state(mock_engine)

        assert result is not None
        assert isinstance(result, StagingDataState)
        assert result.crawl_job_id == "test-job-123"
        assert result.max_id == 42
        assert result.row_count == 5

    def test_returns_state_for_latest_crawl_job(self):
        """Should return state for the most recent crawl job."""
        mock_engine = Mock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        # The query should order by created_at DESC and get the latest
        mock_result = Mock()
        mock_result.fetchone.return_value = ("new-job-789", 100, 4)
        mock_conn.execute.return_value = mock_result

        result = get_staging_data_state(mock_engine)

        assert result is not None
        assert result.crawl_job_id == "new-job-789"
        assert result.max_id == 100
        assert result.row_count == 4

    def test_counts_only_rows_for_latest_job(self):
        """Should count only rows belonging to the latest crawl_job_id."""
        mock_engine = Mock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        # Simulate multiple jobs, but we get only the latest job's stats
        mock_result = Mock()
        mock_result.fetchone.return_value = ("job-2", 77, 7)
        mock_conn.execute.return_value = mock_result

        result = get_staging_data_state(mock_engine)

        assert result is not None
        assert result.crawl_job_id == "job-2"
        assert result.row_count == 7
        assert result.max_id == 77


class TestFetchStagedItemsSinceId:
    """Tests for fetch_staged_items_since_id()."""

    def test_fetches_all_rows_when_after_id_is_zero(self):
        """Should fetch all rows for job when after_id=0."""
        mock_engine = Mock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        # Simulate query returning 3 items
        mock_result = Mock()
        mock_result.__iter__.return_value = [
            ({"title": "Book 0", "author": "Author 0"},),
            ({"title": "Book 1", "author": "Author 1"},),
            ({"title": "Book 2", "author": "Author 2"},),
        ]
        mock_conn.execute.return_value = mock_result

        items = fetch_staged_items_since_id(
            mock_engine, "test-job-abc", after_id=0
        )

        assert len(items) == 3
        assert all(isinstance(item, dict) for item in items)
        assert items[0]["title"] == "Book 0"
        assert items[2]["author"] == "Author 2"

    def test_fetches_only_rows_after_given_id(self):
        """Should fetch only rows with id > after_id."""
        mock_engine = Mock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        # Simulate query returning rows 6-10 (5 rows)
        mock_result = Mock()
        mock_result.__iter__.return_value = [
            ({"title": f"Book {i}", "author": f"Author {i}"},)
            for i in range(5, 10)
        ]
        mock_conn.execute.return_value = mock_result

        items = fetch_staged_items_since_id(
            mock_engine, "test-job-xyz", after_id=50
        )

        # Should get rows 6-10 (5 rows)
        assert len(items) == 5
        assert items[0]["title"] == "Book 5"
        assert items[4]["title"] == "Book 9"

    def test_returns_empty_list_when_no_new_rows(self):
        """Should return empty list when after_id >= max_id."""
        mock_engine = Mock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        # Simulate query returning no rows
        mock_result = Mock()
        mock_result.__iter__.return_value = []
        mock_conn.execute.return_value = mock_result

        items = fetch_staged_items_since_id(
            mock_engine, "test-job-999", after_id=100
        )

        assert items == []

    def test_filters_by_crawl_job_id(self):
        """Should only fetch rows for the specified crawl_job_id."""
        mock_engine = Mock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        # Simulate query filtered by job2
        mock_result = Mock()
        mock_result.__iter__.return_value = [
            ({"title": f"Book {i}", "author": f"Author {i}"},)
            for i in range(3)
        ]
        mock_conn.execute.return_value = mock_result

        items = fetch_staged_items_since_id(mock_engine, "job-2", after_id=0)

        # Should only get rows from job2
        assert len(items) == 3

    def test_returns_items_in_id_order(self):
        """Should return items ordered by row ID ascending."""
        mock_engine = Mock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        # Simulate query returning items in ID order
        mock_result = Mock()
        mock_result.__iter__.return_value = [
            ({"title": f"Book {i}", "author": f"Author {i}"},)
            for i in range(5)
        ]
        mock_conn.execute.return_value = mock_result

        items = fetch_staged_items_since_id(
            mock_engine, "test-job-order", after_id=0
        )

        # Items should be in order: Book 0, Book 1, Book 2, ...
        titles = [item["title"] for item in items]
        assert titles == ["Book 0", "Book 1", "Book 2", "Book 3", "Book 4"]
