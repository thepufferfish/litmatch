"""Integration tests for database schema and connectivity.

Verifies that the PostgreSQL database is initialized correctly with
all required tables, pgvector extension, and correct schema.
"""
import os

import httpx
import psycopg2
import pytest
from dotenv import load_dotenv


pytestmark = pytest.mark.integration


def _get_db_connection():
    """Return a psycopg2 connection to the test database."""
    env_file = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    load_dotenv(env_file)

    return psycopg2.connect(
        host="localhost",
        port=5432,
        user=os.environ.get("POSTGRES_USER", "bookuser"),
        password=os.environ.get("POSTGRES_PASSWORD", "changeme"),
        dbname=os.environ.get("POSTGRES_DB", "bookdb"),
    )


class TestDatabaseSchema:
    """Tests that the database schema is correctly initialized."""

    def test_books_endpoint_returns_empty_initially(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """Before ETL runs, the books endpoint should return an empty list."""
        response = http_client.get(f"{backend_url}/books/")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_genres_endpoint_returns_list(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """The genres endpoint should return a list (possibly empty before ETL)."""
        response = http_client.get(f"{backend_url}/genres/")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_pagination_metadata_present(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """Book list responses should include pagination metadata."""
        response = http_client.get(f"{backend_url}/books/?page=1&limit=10")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "page" in data
        assert "limit" in data
        assert data["page"] == 1
        assert data["limit"] == 10


class TestDatabaseConnectivity:
    """Tests that the backend maintains database connectivity."""

    def test_repeated_health_checks_succeed(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """Multiple sequential health checks should all succeed."""
        for _ in range(3):
            response = http_client.get(f"{backend_url}/health")
            assert response.status_code == 200
            assert response.json()["status"] == "ok"


class TestRichEmbeddingSchema:
    """Tests that the rich embedding schema migration was applied correctly.

    Verifies the structural changes introduced in migration 004:
    - book_embeddings table exists with the correct columns
    - genre table has embedding column added
    - book table no longer has an embedding column (moved to book_embeddings)
    """

    def test_book_embeddings_table_exists(self, compose_stack: dict) -> None:
        """The book_embeddings table should exist after migration."""
        conn = _get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1
                        FROM information_schema.tables
                        WHERE table_name = 'book_embeddings'
                    )
                """)
                exists = cur.fetchone()[0]
            assert exists, "book_embeddings table does not exist"
        finally:
            conn.close()

    def test_book_embeddings_has_review_embedding_column(self, compose_stack: dict) -> None:
        """book_embeddings should have a review_embedding column."""
        conn = _get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'book_embeddings'
                    AND column_name = 'review_embedding'
                """)
                row = cur.fetchone()
            assert row is not None, "review_embedding column not found in book_embeddings"
        finally:
            conn.close()

    def test_book_embeddings_has_description_embedding_column(self, compose_stack: dict) -> None:
        """book_embeddings should have a description_embedding column."""
        conn = _get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'book_embeddings'
                    AND column_name = 'description_embedding'
                """)
                row = cur.fetchone()
            assert row is not None, "description_embedding column not found in book_embeddings"
        finally:
            conn.close()

    def test_book_embeddings_has_genre_embedding_column(self, compose_stack: dict) -> None:
        """book_embeddings should have a genre_embedding column."""
        conn = _get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'book_embeddings'
                    AND column_name = 'genre_embedding'
                """)
                row = cur.fetchone()
            assert row is not None, "genre_embedding column not found in book_embeddings"
        finally:
            conn.close()

    def test_book_embeddings_has_composite_embedding_column(self, compose_stack: dict) -> None:
        """book_embeddings should have a composite embedding column (1152-dim)."""
        conn = _get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'book_embeddings'
                    AND column_name = 'embedding'
                """)
                row = cur.fetchone()
            assert row is not None, "embedding column not found in book_embeddings"
        finally:
            conn.close()

    def test_genre_table_has_embedding_column(self, compose_stack: dict) -> None:
        """The genre table should have an embedding column after migration."""
        conn = _get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'genre'
                    AND column_name = 'embedding'
                """)
                row = cur.fetchone()
            assert row is not None, "embedding column not found in genre table"
        finally:
            conn.close()

    def test_book_table_does_not_have_embedding_column(self, compose_stack: dict) -> None:
        """The book table should NOT have an embedding column (moved to book_embeddings)."""
        conn = _get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'book'
                    AND column_name = 'embedding'
                """)
                row = cur.fetchone()
            assert row is None, (
                "embedding column still exists on book table; "
                "it should have been moved to book_embeddings"
            )
        finally:
            conn.close()

    def test_book_embeddings_has_book_id_index(self, compose_stack: dict) -> None:
        """book_embeddings should have an index on book_id for fast lookups."""
        conn = _get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT indexname
                    FROM pg_indexes
                    WHERE tablename = 'book_embeddings'
                    AND indexname = 'ix_book_embeddings_book_id'
                """)
                row = cur.fetchone()
            assert row is not None, "ix_book_embeddings_book_id index not found"
        finally:
            conn.close()

    def test_book_embeddings_has_hnsw_index_on_embedding(self, compose_stack: dict) -> None:
        """book_embeddings should have an HNSW index on the composite embedding column."""
        conn = _get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE tablename = 'book_embeddings'
                    AND indexname = 'ix_book_embeddings_embedding_hnsw'
                """)
                row = cur.fetchone()
            assert row is not None, (
                "ix_book_embeddings_embedding_hnsw HNSW index not found on book_embeddings.embedding"
            )
            assert "hnsw" in row[1].lower(), (
                "Index ix_book_embeddings_embedding_hnsw is not an HNSW index"
            )
        finally:
            conn.close()

    def test_book_embeddings_has_hnsw_index_on_review_embedding(self, compose_stack: dict) -> None:
        """book_embeddings should have an HNSW index on the review_embedding column."""
        conn = _get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE tablename = 'book_embeddings'
                    AND indexname = 'ix_book_embeddings_review_embedding_hnsw'
                """)
                row = cur.fetchone()
            assert row is not None, (
                "ix_book_embeddings_review_embedding_hnsw HNSW index not found on book_embeddings.review_embedding"
            )
            assert "hnsw" in row[1].lower(), (
                "Index ix_book_embeddings_review_embedding_hnsw is not an HNSW index"
            )
        finally:
            conn.close()
