"""Shared helpers for integration tests.

Provides utilities for waiting on services, checking container health,
and interacting with the compose stack during tests.
"""
import subprocess
import time
from typing import Literal

import httpx

# Default timeouts for service readiness
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_POLL_INTERVAL_SECONDS = 3

# Service endpoints (matching compose port mappings)
BACKEND_URL = "http://localhost:8000"
DAGSTER_URL = "http://localhost:3000"


ServiceName = Literal["db", "backend", "dagster-code", "dagster-webserver", "dagster-daemon"]


def wait_for_http(
    url: str,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    poll_interval: int = DEFAULT_POLL_INTERVAL_SECONDS,
) -> bool:
    """Wait for an HTTP endpoint to return a 2xx status.

    Args:
        url: The URL to poll.
        timeout: Maximum seconds to wait.
        poll_interval: Seconds between polls.

    Returns:
        True if the endpoint responded with 2xx within the timeout.

    Raises:
        TimeoutError: If the endpoint did not respond within the timeout.
    """
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            response = httpx.get(url, timeout=5)
            if response.is_success:
                return True
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout):
            pass
        time.sleep(poll_interval)

    raise TimeoutError(f"Service at {url} did not become ready within {timeout}s")


def get_container_health(service_name: ServiceName, project: str = "litmatch-test") -> str:
    """Get the health status of a compose service container.

    Args:
        service_name: The compose service name.
        project: The compose project name.

    Returns:
        Health status string: "healthy", "unhealthy", "starting", or "none".
    """
    result = subprocess.run(
        [
            "podman", "compose", "-p", project,
            "ps", "--format", "json", service_name,
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return "none"

    import json
    try:
        containers = json.loads(result.stdout)
        if not containers:
            return "none"
        container = containers[0] if isinstance(containers, list) else containers
        health = container.get("Health", container.get("Status", "none"))
        return health.lower() if isinstance(health, str) else "none"
    except (json.JSONDecodeError, IndexError, KeyError):
        return "none"


def is_compose_stack_running(project: str = "litmatch-test") -> bool:
    """Check if the compose stack has running containers.

    Args:
        project: The compose project name.

    Returns:
        True if at least one container is running.
    """
    result = subprocess.run(
        ["podman", "compose", "-p", project, "ps", "-q"],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())


def compose_command(
    *args: str,
    project: str = "litmatch-test",
    env_file: str = ".env",
) -> subprocess.CompletedProcess:
    """Run a podman compose command with the test project config.

    Args:
        args: Additional arguments to pass to podman compose.
        project: The compose project name.
        env_file: Path to the env file.

    Returns:
        The completed process result.
    """
    cmd = [
        "podman", "compose",
        "-f", "compose.yaml",
        "-f", "compose.test.yaml",
        "--env-file", env_file,
        "-p", project,
        *args,
    ]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=300)
