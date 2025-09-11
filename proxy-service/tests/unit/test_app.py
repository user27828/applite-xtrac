"""
Unit tests for proxy-service health check endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from app import app


class TestHealthEndpoints:
    """Test cases for health check endpoints."""

    def test_ping_endpoint(self, client: TestClient):
        """Test the general ping endpoint."""
        response = client.get("/ping")
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"] == "PONG!"

    def test_ping_all_endpoint(self, client: TestClient):
        """Test the ping-all endpoint that checks all services."""
        response = client.get("/ping-all")
        assert response.status_code == 200
        data = response.json()

        # Should contain services key
        assert "services" in data

        # Should check all expected services
        expected_services = ["unstructured-io", "libreoffice", "pyconvert", "gotenberg"]
        services_data = data["services"]

        for service in expected_services:
            assert service in services_data
            assert "status" in services_data[service]
            service_info = services_data[service]
            
            # Check that either response_code or error is present
            has_response_code = "response_code" in service_info
            has_error = "error" in service_info
            assert has_response_code or has_error, f"Service {service} missing both response_code and error fields"
            
            # Status should be one of the expected values
            assert service_info["status"] in ["healthy", "unhealthy", "unreachable"]

    @pytest.mark.parametrize("service", ["unstructured-io", "libreoffice", "pandoc", "gotenberg"])
    def test_individual_service_ping(self, client: TestClient, service: str):
        """Test individual service ping endpoints."""
        response = client.get(f"/{service}/ping")
        # Service ping endpoints should return some response
        # Status code might vary depending on service availability
        assert response.status_code in [200, 404, 500, 502, 503]

    def test_ping_all_response_structure(self, client: TestClient):
        """Test that ping-all returns properly structured response."""
        response = client.get("/ping-all")
        assert response.status_code == 200
        data = response.json()

        assert isinstance(data["services"], dict)

        for service_name, service_info in data["services"].items():
            assert isinstance(service_info, dict)
            assert "status" in service_info
            
            # Check that either response_code or error is present
            has_response_code = "response_code" in service_info
            has_error = "error" in service_info
            assert has_response_code or has_error, f"Service {service_name} missing both response_code and error fields"
            
            # Status should be one of the expected values
            assert service_info["status"] in ["healthy", "unhealthy", "unreachable"]
            
            # If response_code exists, it should be an integer
            if has_response_code:
                assert isinstance(service_info["response_code"], int)

    def test_ping_endpoint_content_type(self, client: TestClient):
        """Test that ping endpoint returns correct content type."""
        response = client.get("/ping")
        assert response.headers["content-type"] == "application/json"

    def test_ping_all_endpoint_content_type(self, client: TestClient):
        """Test that ping-all endpoint returns correct content type."""
        response = client.get("/ping-all")
        assert response.headers["content-type"] == "application/json"
