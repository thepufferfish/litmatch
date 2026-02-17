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

# Job name for the standalone embedding pipeline
EMBEDDING_PIPELINE_JOB_NAME = "embedding_pipeline"

# Repository location for GraphQL queries
REPO_LOCATION = "litmatch.definitions"
REPO_NAME = "__repository__"

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


def _query_asset_graph(dagster_url: str, http_client: httpx.Client) -> dict:
    """Query the Dagster asset graph for all registered assets.

    Args:
        dagster_url: Base URL of the Dagster webserver.
        http_client: httpx client for making requests.

    Returns:
        The parsed JSON data from the GraphQL response.
    """
    query = """
    query AssetGraph {
        assetNodes {
            assetKey {
                path
            }
            description
        }
    }
    """
    response = http_client.post(
        f"{dagster_url}{GRAPHQL_PATH}",
        json={"query": query},
        timeout=30,
    )
    assert response.status_code == 200, f"Asset graph query failed: {response.text}"
    return response.json()


def _query_job_asset_keys(
    dagster_url: str,
    http_client: httpx.Client,
    job_name: str,
) -> list[str]:
    """Query the assets selected by a specific Dagster job.

    Args:
        dagster_url: Base URL of the Dagster webserver.
        http_client: httpx client for making requests.
        job_name: The name of the job to inspect.

    Returns:
        List of flattened asset key paths (e.g., ["review_embeddings"]).
    """
    query = """
    query JobAssets($selector: PipelineSelector!) {
        pipelineOrError(params: $selector) {
            __typename
            ... on Pipeline {
                solids {
                    name
                }
            }
        }
    }
    """
    variables = {
        "selector": {
            "pipelineName": job_name,
            "repositoryLocationName": REPO_LOCATION,
            "repositoryName": REPO_NAME,
        }
    }
    response = http_client.post(
        f"{dagster_url}{GRAPHQL_PATH}",
        json={"query": query, "variables": variables},
        timeout=30,
    )
    assert response.status_code == 200, f"Job query failed: {response.text}"
    data = response.json()
    pipeline = data.get("data", {}).get("pipelineOrError", {})
    solids = pipeline.get("solids", [])
    return [s["name"] for s in solids]


class TestEmbeddingAssetRegistration:
    """Tests that the new rich embedding assets appear in the Dagster asset graph."""

    # All new assets introduced by the rich embedding pipeline
    EXPECTED_EMBEDDING_ASSETS = {
        "genre_embeddings",
        "book_description_embeddings",
        "book_genre_embeddings",
        "composite_book_embeddings",
    }

    # Pre-existing embedding assets that must still be present
    EXISTING_EMBEDDING_ASSETS = {
        "review_embeddings",
        "book_embeddings",
    }

    def test_new_embedding_assets_in_asset_graph(
        self, dagster_url: str, http_client: httpx.Client
    ) -> None:
        """All four new embedding assets should appear in the Dagster asset graph."""
        data = _query_asset_graph(dagster_url, http_client)
        asset_nodes = data.get("data", {}).get("assetNodes", [])

        # Flatten each asset's key path into a single string
        registered_keys = {
            "/".join(node["assetKey"]["path"]) for node in asset_nodes
        }

        for asset_key in self.EXPECTED_EMBEDDING_ASSETS:
            assert asset_key in registered_keys, (
                f"Expected embedding asset '{asset_key}' not found in asset graph. "
                f"Registered assets: {sorted(registered_keys)}"
            )

    def test_existing_embedding_assets_still_registered(
        self, dagster_url: str, http_client: httpx.Client
    ) -> None:
        """Pre-existing review and book embedding assets remain in the asset graph."""
        data = _query_asset_graph(dagster_url, http_client)
        asset_nodes = data.get("data", {}).get("assetNodes", [])

        registered_keys = {
            "/".join(node["assetKey"]["path"]) for node in asset_nodes
        }

        for asset_key in self.EXISTING_EMBEDDING_ASSETS:
            assert asset_key in registered_keys, (
                f"Existing embedding asset '{asset_key}' missing from asset graph"
            )

    def test_embedding_pipeline_job_includes_new_assets(
        self, dagster_url: str, http_client: httpx.Client
    ) -> None:
        """The embedding_pipeline job should include all new embedding assets."""
        asset_names = _query_job_asset_keys(
            dagster_url, http_client, EMBEDDING_PIPELINE_JOB_NAME
        )

        for asset_key in self.EXPECTED_EMBEDDING_ASSETS:
            assert asset_key in asset_names, (
                f"Expected asset '{asset_key}' not found in embedding_pipeline job. "
                f"Job assets: {sorted(asset_names)}"
            )

    def test_etl_pipeline_job_includes_new_assets(
        self, dagster_url: str, http_client: httpx.Client
    ) -> None:
        """The etl_pipeline job should also include all new embedding assets."""
        asset_names = _query_job_asset_keys(
            dagster_url, http_client, ETL_JOB_NAME
        )

        for asset_key in self.EXPECTED_EMBEDDING_ASSETS:
            assert asset_key in asset_names, (
                f"Expected asset '{asset_key}' not found in etl_pipeline job. "
                f"Job assets: {sorted(asset_names)}"
            )
