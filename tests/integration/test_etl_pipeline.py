"""Integration tests for the Dagster ETL pipeline.

Verifies that the ETL pipeline can be triggered via the Dagster GraphQL API,
processes the test fixture data, and loads books into the database.
"""
import time

import httpx
import pytest


pytestmark = pytest.mark.integration

# GraphQL endpoint for Dagster
GRAPHQL_PATH = "/graphql"

# The ETL pipeline job name as defined in the sensor module
ETL_JOB_NAME = "etl_pipeline"

# Maximum time to wait for a pipeline run to complete
RUN_TIMEOUT_SECONDS = 180
RUN_POLL_INTERVAL_SECONDS = 5


def _trigger_etl_run(dagster_url: str, http_client: httpx.Client) -> str:
    """Trigger an ETL pipeline run via Dagster's GraphQL API.

    Args:
        dagster_url: Base URL of the Dagster webserver.
        http_client: httpx client for making requests.

    Returns:
        The run ID of the launched pipeline run.

    Raises:
        AssertionError: If the launch request fails.
    """
    mutation = """
    mutation LaunchRun($selector: JobOrPipelineSelector!) {
        launchRun(executionParams: {selector: $selector}) {
            __typename
            ... on LaunchRunSuccess {
                run {
                    runId
                }
            }
            ... on PythonError {
                message
                stack
            }
            ... on RunConfigValidationInvalid {
                errors {
                    message
                }
            }
        }
    }
    """

    variables = {
        "selector": {
            "jobName": ETL_JOB_NAME,
            "repositoryLocationName": "litmatch.definitions",
            "repositoryName": "__repository__",
        }
    }

    response = http_client.post(
        f"{dagster_url}{GRAPHQL_PATH}",
        json={"query": mutation, "variables": variables},
        timeout=30,
    )

    assert response.status_code == 200, f"GraphQL request failed: {response.text}"
    data = response.json()

    launch_result = data.get("data", {}).get("launchRun", {})
    typename = launch_result.get("__typename", "")

    assert typename == "LaunchRunSuccess", (
        f"Failed to launch ETL run: {launch_result}"
    )

    return launch_result["run"]["runId"]


def _wait_for_run_completion(
    dagster_url: str,
    http_client: httpx.Client,
    run_id: str,
    timeout: int = RUN_TIMEOUT_SECONDS,
) -> str:
    """Wait for a Dagster pipeline run to complete.

    Args:
        dagster_url: Base URL of the Dagster webserver.
        http_client: httpx client for making requests.
        run_id: The run ID to monitor.
        timeout: Maximum seconds to wait.

    Returns:
        The final run status (e.g., "SUCCESS", "FAILURE").

    Raises:
        TimeoutError: If the run does not complete within the timeout.
    """
    query = """
    query RunStatus($runId: ID!) {
        runOrError(runId: $runId) {
            __typename
            ... on Run {
                status
            }
        }
    }
    """

    terminal_statuses = {"SUCCESS", "FAILURE", "CANCELED"}
    deadline = time.time() + timeout

    while time.time() < deadline:
        response = http_client.post(
            f"{dagster_url}{GRAPHQL_PATH}",
            json={"query": query, "variables": {"runId": run_id}},
            timeout=30,
        )

        if response.status_code == 200:
            run_data = response.json().get("data", {}).get("runOrError", {})
            status = run_data.get("status", "")
            if status in terminal_statuses:
                return status

        time.sleep(RUN_POLL_INTERVAL_SECONDS)

    raise TimeoutError(f"Run {run_id} did not complete within {timeout}s")


class TestEtlPipelineExecution:
    """Tests for running the full ETL pipeline against the test stack."""

    @pytest.fixture(scope="class")
    def etl_run_result(
        self, dagster_url: str, backend_url: str, http_client: httpx.Client
    ) -> dict:
        """Trigger the ETL pipeline and wait for it to complete.

        Returns a dict with run_id and status. This is class-scoped so
        the ETL only runs once for all tests in this class.
        """
        run_id = _trigger_etl_run(dagster_url, http_client)
        status = _wait_for_run_completion(dagster_url, http_client, run_id)
        return {"run_id": run_id, "status": status}

    def test_etl_run_succeeds(self, etl_run_result: dict) -> None:
        """The ETL pipeline should complete with SUCCESS status."""
        assert etl_run_result["status"] == "SUCCESS"

    def test_books_loaded_after_etl(
        self, etl_run_result: dict, backend_url: str, http_client: httpx.Client
    ) -> None:
        """After ETL completes, the books endpoint should return loaded books."""
        # Ensure ETL succeeded first
        assert etl_run_result["status"] == "SUCCESS"

        response = http_client.get(f"{backend_url}/books/?limit=100")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3  # 3 books in fixture JSONL

    def test_loaded_books_have_correct_titles(
        self, etl_run_result: dict, backend_url: str, http_client: httpx.Client
    ) -> None:
        """The loaded books should match the titles in the fixture data."""
        assert etl_run_result["status"] == "SUCCESS"

        response = http_client.get(f"{backend_url}/books/?limit=100")
        data = response.json()

        expected_titles = {
            "Death and the Gardener",
            "Girl on Girl",
            "Intermezzo",
        }
        actual_titles = {book["title"] for book in data["items"]}
        assert actual_titles == expected_titles

    def test_books_have_authors(
        self, etl_run_result: dict, backend_url: str, http_client: httpx.Client
    ) -> None:
        """Loaded books should have associated author data."""
        assert etl_run_result["status"] == "SUCCESS"

        response = http_client.get(f"{backend_url}/books/?limit=100")
        data = response.json()

        for book in data["items"]:
            assert book["author"] is not None
            assert book["author"]["name"] != ""

    def test_books_have_genres(
        self, etl_run_result: dict, backend_url: str, http_client: httpx.Client
    ) -> None:
        """Loaded books should have associated genre data."""
        assert etl_run_result["status"] == "SUCCESS"

        response = http_client.get(f"{backend_url}/books/?limit=100")
        data = response.json()

        # At least one book should have genres
        books_with_genres = [b for b in data["items"] if len(b["genres"]) > 0]
        assert len(books_with_genres) >= 1

    def test_genres_endpoint_populated(
        self, etl_run_result: dict, backend_url: str, http_client: httpx.Client
    ) -> None:
        """After ETL, the genres endpoint should return the fixture genres."""
        assert etl_run_result["status"] == "SUCCESS"

        response = http_client.get(f"{backend_url}/genres/")

        assert response.status_code == 200
        genres = response.json()
        genre_names = {g["name"] for g in genres}
        # At minimum, Fiction and Non-Fiction should be present from fixtures
        assert "Fiction" in genre_names
        assert "Non-Fiction" in genre_names

    def test_reviews_loaded_for_book(
        self, etl_run_result: dict, backend_url: str, http_client: httpx.Client
    ) -> None:
        """After ETL, books should have associated reviews."""
        assert etl_run_result["status"] == "SUCCESS"

        # Get the first book
        response = http_client.get(f"{backend_url}/books/?limit=1")
        books = response.json()["items"]
        assert len(books) > 0

        book_id = books[0]["id"]
        response = http_client.get(f"{backend_url}/reviews/{book_id}")

        assert response.status_code == 200
        reviews = response.json()
        assert len(reviews) > 0
