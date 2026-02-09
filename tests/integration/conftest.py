"""Session-scoped fixtures for integration tests.

These fixtures manage the lifecycle of the Podman compose test stack.
The stack starts once per test session and is torn down at the end.
"""
import os
import subprocess

import httpx
import pytest

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
