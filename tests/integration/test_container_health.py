"""Integration tests for container health checks.

Verifies that all compose services start, become healthy,
and respond on their expected ports.
"""
import httpx
import pytest


pytestmark = pytest.mark.integration


class TestBackendHealth:
    """Tests for the FastAPI backend service health."""

    def test_health_endpoint_returns_ok(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """The /health endpoint should return 200 with status ok."""
        response = http_client.get(f"{backend_url}/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"

    def test_health_confirms_database_connectivity(
        self, backend_url: str, http_client: httpx.Client
    ) -> None:
        """The health endpoint verifies database connectivity (not just HTTP)."""
        response = http_client.get(f"{backend_url}/health")

        # If DB is unreachable, backend returns 503
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


class TestDagsterHealth:
    """Tests for the Dagster webserver service health."""

    def test_server_info_returns_200(
        self, dagster_url: str, http_client: httpx.Client
    ) -> None:
        """The /server_info endpoint should return 200."""
        response = http_client.get(f"{dagster_url}/server_info")

        assert response.status_code == 200

    def test_server_info_contains_version(
        self, dagster_url: str, http_client: httpx.Client
    ) -> None:
        """The /server_info response should include Dagster version information."""
        response = http_client.get(f"{dagster_url}/server_info")

        data = response.json()
        assert "dagster_version" in data or "version" in data


class TestServicePorts:
    """Tests that services are reachable on expected ports."""

    def test_backend_reachable_on_port_8000(
        self, http_client: httpx.Client
    ) -> None:
        """Backend should be accessible on port 8000."""
        response = http_client.get("http://localhost:8000/health")
        assert response.status_code == 200

    def test_dagster_reachable_on_port_3000(
        self, http_client: httpx.Client
    ) -> None:
        """Dagster webserver should be accessible on port 3000."""
        response = http_client.get("http://localhost:3000/server_info")
        assert response.status_code == 200
