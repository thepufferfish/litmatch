"""Session-scoped fixtures for integration tests.

These fixtures manage the lifecycle of the Podman compose test stack.
The stack starts once per test session and is torn down at the end.
"""
import json
import os
import subprocess

import httpx
import psycopg2
import pytest
from psycopg2.extras import Json

from tests.integration.helpers import (
    BACKEND_URL,
    DAGSTER_URL,
    compose_command,
    wait_for_http,
)

# Project name isolates test containers from development containers
TEST_PROJECT = "litmatch-test"


def _stack_is_available() -> bool:
    """Check if podman and compose are available on this system."""
    try:
        result = subprocess.run(
            ["podman", "compose", "version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _seed_staging_table() -> None:
    """Insert test fixture data into the staging table for integration tests."""
    from dotenv import load_dotenv

    env_file = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    load_dotenv(env_file)

    db_user = os.environ.get("POSTGRES_USER", "bookuser")
    db_pass = os.environ.get("POSTGRES_PASSWORD", "changeme")
    db_name = os.environ.get("POSTGRES_DB", "bookdb")

    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        user=db_user,
        password=db_pass,
        dbname=db_name,
    )
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS raw_books_staging (
                    id SERIAL PRIMARY KEY,
                    crawl_job_id VARCHAR(64) NOT NULL,
                    item_data JSONB NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    url TEXT
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_staging_crawl_job_id ON raw_books_staging (crawl_job_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_staging_created_at ON raw_books_staging (created_at)")

            fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "books.jsonl")
            with open(fixture_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    item = json.loads(line)
                    cur.execute(
                        "INSERT INTO raw_books_staging (crawl_job_id, item_data, url) VALUES (%s, %s, %s)",
                        ("test-fixture-crawl", Json(item), item.get("url", "")),
                    )
            conn.commit()
    finally:
        conn.close()


@pytest.fixture(scope="session")
def compose_stack():
    """Start the compose test stack and yield when all services are healthy.

    Tears down the stack (with volumes) after the test session completes.
    Skip if podman/compose is not available.
    """
    if not _stack_is_available():
        pytest.skip("podman compose not available on this system")

    # Check for .env file
    env_file = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    if not os.path.exists(env_file):
        pytest.skip(".env file not found; required for compose stack")

    # Start the stack
    result = compose_command("up", "--build", "-d", project=TEST_PROJECT)
    if result.returncode != 0:
        pytest.fail(f"Failed to start compose stack: {result.stderr}")

    try:
        # Wait for backend health endpoint
        wait_for_http(f"{BACKEND_URL}/health", timeout=120)

        # Wait for Dagster webserver
        wait_for_http(f"{DAGSTER_URL}/server_info", timeout=120)

        # Seed the staging table with fixture data
        _seed_staging_table()

        yield {
            "backend_url": BACKEND_URL,
            "dagster_url": DAGSTER_URL,
            "project": TEST_PROJECT,
        }
    except TimeoutError as exc:
        # Capture logs before failing
        log_result = compose_command("logs", "--tail", "50", project=TEST_PROJECT)
        pytest.fail(f"Services did not become healthy: {exc}\n\nLogs:\n{log_result.stdout}")
    finally:
        # Tear down with volumes for clean state
        compose_command("down", "-v", project=TEST_PROJECT)


@pytest.fixture(scope="session")
def backend_url(compose_stack: dict) -> str:
    """Return the backend base URL from the running compose stack."""
    return compose_stack["backend_url"]


@pytest.fixture(scope="session")
def dagster_url(compose_stack: dict) -> str:
    """Return the Dagster webserver base URL from the running compose stack."""
    return compose_stack["dagster_url"]


@pytest.fixture(scope="session")
def http_client() -> httpx.Client:
    """Provide a reusable httpx client for the test session."""
    with httpx.Client(timeout=30) as client:
        yield client
