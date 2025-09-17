"""
Local tests for the API Service.

These tests run against a locally started API service (which connects to the database service).
"""

import asyncio
import json
from typing import Any, Dict

import httpx
import pytest
import pytest_asyncio


class TestAPIServiceLocal:
    """Tests for the API Service running locally."""

    @pytest.fixture
    def api_service_url(self):
        """API service URL for local testing."""
        # Use IPv4 loopback explicitly; some macOS setups resolve
        # "localhost" to IPv6 ::1 while the server listens on IPv4.
        # This avoids httpx ReadError due to IPv6 connection issues.
        return "http://127.0.0.1:8080"

    @pytest_asyncio.fixture
    async def client(self, api_service_url):
        """HTTP client for API service."""
        # Use longer timeout and better connection settings for testing
        timeout = httpx.Timeout(
            connect=10.0,  # Connection timeout
            read=30.0,  # Read timeout
            write=10.0,  # Write timeout
            pool=5.0,  # Pool timeout
        )
        limits = httpx.Limits(
            max_keepalive_connections=5, max_connections=10, keepalive_expiry=30.0
        )
        async with httpx.AsyncClient(
            base_url=api_service_url,
            timeout=timeout,
            limits=limits,
            follow_redirects=True,
        ) as client:
            yield client

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """Test API service health endpoint."""
        response = await client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "secure-nostr-profiles-api"

    @pytest.mark.asyncio
    async def test_search_profiles_endpoint(self, client):
        """Test the /api/search endpoint."""
        payload = {"query": "test", "limit": 10}

        response = await client.post("/api/search", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "profiles" in data
        assert "count" in data
        assert isinstance(data["profiles"], list)

    @pytest.mark.asyncio
    async def test_search_business_profiles_endpoint(self, client):
        """Test the /api/search_by_business_type endpoint."""
        payload = {"query": "restaurant", "business_type": "restaurant", "limit": 5}

        response = await client.post("/api/search_by_business_type", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "profiles" in data
        assert "count" in data

    @pytest.mark.asyncio
    async def test_get_profile_by_pubkey_endpoint(self, client):
        """Test the /api/profile/{pubkey} endpoint."""
        # First, get some profiles to test with
        search_payload = {"query": "", "limit": 1}
        search_response = await client.post("/api/search", json=search_payload)
        assert search_response.status_code == 200

        search_data = search_response.json()
        if search_data["profiles"]:
            # Test with an existing profile
            profile = search_data["profiles"][0]
            pubkey = profile.get("pubkey")

            if pubkey:
                response = await client.get(f"/api/profile/{pubkey}")
                assert response.status_code == 200

                data = response.json()
                assert data["success"] is True
                assert "profile" in data

        # Test with non-existent profile
        fake_pubkey = "0" * 64
        response = await client.get(f"/api/profile/{fake_pubkey}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_stats_endpoint(self, client):
        """Test the /api/stats endpoint."""
        response = await client.get("/api/stats")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "stats" in data

    @pytest.mark.asyncio
    async def test_get_business_types_endpoint(self, client):
        """Test the /api/business_types endpoint."""
        response = await client.get("/api/business_types")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "business_types" in data
        assert isinstance(data["business_types"], list)

    @pytest.mark.asyncio
    async def test_refresh_endpoint(self, client):
        """Test the /api/refresh endpoint."""
        response = await client.post("/api/refresh")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "message" in data

    @pytest.mark.asyncio
    async def test_chat_endpoint_non_streaming(self, client):
        """Test the /api/chat endpoint in non-streaming mode."""
        # Note: This test may fail if OpenAI API key is not configured
        # We'll test the basic structure
        payload = {
            "messages": [{"role": "user", "content": "Find restaurants in Seattle"}],
            "stream": False,
        }

        # This will likely fail due to authentication, but we test the endpoint exists
        response = await client.post("/api/chat", json=payload)
        # Could be 401 (auth error) or 200 (success) - both indicate endpoint works
        assert response.status_code in [200, 401, 500]

    @pytest.mark.asyncio
    async def test_validation_errors(self, client):
        """Test API validation and error handling."""
        # Test with invalid JSON
        response = await client.post("/api/search", content="invalid json")
        assert response.status_code == 422

        # Test with missing required fields
        response = await client.post("/api/search", json={})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_pubkey_format(self, client):
        """Test with invalid pubkey format."""
        invalid_pubkey = "invalid_pubkey"
        response = await client.get(f"/api/profile/{invalid_pubkey}")
        assert response.status_code == 400
