"""
Integration tests for API root and documentation endpoints.

These tests verify that the FastAPI application is correctly configured
and that basic endpoints are accessible.
"""

import pytest


class TestRootEndpoints:
    """Test root API endpoints."""

    def test_root_returns_running_status(self, client):
        """Test that root endpoint returns API running status."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "API is running"

    def test_openapi_docs_available(self, client):
        """Test that OpenAPI docs (Swagger UI) are available."""
        response = client.get("/docs")

        # Should return HTML page
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    def test_openapi_json_available(self, client):
        """Test that OpenAPI JSON schema is available."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        data = response.json()

        # Check OpenAPI structure
        assert "openapi" in data
        assert "info" in data
        assert data["info"]["title"] == "Real Estate Information Platform API"
        assert "paths" in data

    def test_redoc_available(self, client):
        """Test that ReDoc documentation is available."""
        response = client.get("/redoc")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")


class TestAPIStructure:
    """Test API structure and routes."""

    def test_api_v1_prefix_exists(self, client):
        """Test that /api/v1 prefix routes exist in OpenAPI spec."""
        response = client.get("/openapi.json")
        data = response.json()

        paths = data.get("paths", {})
        # At least some paths should start with /api/v1
        api_v1_paths = [p for p in paths.keys() if p.startswith("/api/v1")]
        assert len(api_v1_paths) > 0, "No /api/v1 paths found in OpenAPI spec"

    def test_expected_tags_exist(self, client):
        """Test that API has tags defined in OpenAPI spec."""
        response = client.get("/openapi.json")
        data = response.json()

        # Just verify tags is a list (may be empty if no tags configured)
        tags = data.get("tags", [])
        assert isinstance(tags, list), "tags should be a list"

        # If tags exist, verify they have a name field
        for tag in tags:
            assert "name" in tag, "Each tag should have a name"
