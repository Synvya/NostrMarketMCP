"""
AWS tests for the API Service.

These tests run against the API service deployed on AWS.
"""

import asyncio
import json
import os
from typing import Any, Dict

import httpx
import pytest
import pytest_asyncio


class TestAPIServiceAWS:
    """Tests for the API Service running on AWS."""

    @pytest.fixture
    def api_service_url(self):
        """API service URL for AWS testing."""
        # This would be the external AWS API URL
        base_url = os.getenv(
            "AWS_API_SERVICE_URL", "https://your-api-gateway-url.amazonaws.com"
        )
        return base_url

    @pytest.fixture
    def api_key(self):
        """API key for AWS testing."""
        return os.getenv("AWS_API_KEY")

    @pytest_asyncio.fixture
    async def client(self, api_service_url, api_key):
        """HTTP client for API service with authentication."""
        headers = {}
        if api_key:
            headers["X-API-Key"] = api_key

        async with httpx.AsyncClient(
            base_url=api_service_url, timeout=60.0, headers=headers
        ) as client:
            yield client

    @pytest.mark.asyncio
    async def test_aws_health_check(self, client):
        """Test API service health endpoint on AWS."""
        response = await client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "secure-nostr-profiles-api"
        assert data["environment"] == "production"

    @pytest.mark.asyncio
    async def test_aws_search_with_real_data(self, client):
        """Test search with real production data."""
        payload = {"query": "restaurant", "limit": 10}

        response = await client.post("/api/search", json=payload)
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert len(data["profiles"]) > 0

        # Check that profiles have expected fields
        profile = data["profiles"][0]
        assert "pubkey" in profile
        assert len(profile["pubkey"]) == 64  # hex format

    @pytest.mark.asyncio
    async def test_aws_business_search_performance(self, client):
        """Test business search performance on AWS."""
        import time

        payload = {"query": "coffee", "business_type": "restaurant", "limit": 15}

        start_time = time.time()
        response = await client.post("/api/search_by_business_type", json=payload)
        end_time = time.time()

        assert response.status_code == 200
        # Should complete within reasonable time
        assert (end_time - start_time) < 10.0

        data = response.json()
        assert data["success"] is True

    @pytest.mark.asyncio
    async def test_aws_stats_with_production_data(self, client):
        """Test stats endpoint with production data."""
        response = await client.get("/api/stats")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        stats = data["stats"]

        # Production should have substantial data
        assert stats["total_profiles"] > 100
        assert stats["profiles_with_name"] > 0
        assert stats["last_updated"] > 0

    @pytest.mark.asyncio
    async def test_aws_get_specific_profile(self, client):
        """Test getting a specific profile on AWS."""
        # First get some profiles to test with
        search_payload = {"query": "", "limit": 1}
        search_response = await client.post("/api/search", json=search_payload)
        assert search_response.status_code == 200

        search_data = search_response.json()
        if search_data["profiles"]:
            profile = search_data["profiles"][0]
            pubkey = profile["pubkey"]

            response = await client.get(f"/api/profile/{pubkey}")
            assert response.status_code == 200

            data = response.json()
            assert data["success"] is True
            assert data["profile"]["pubkey"] == pubkey

    @pytest.mark.asyncio
    async def test_aws_business_types(self, client):
        """Test business types endpoint on AWS."""
        response = await client.get("/api/business_types")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        business_types = data["business_types"]

        # Should have the standard business types
        expected_types = [
            "retail",
            "restaurant",
            "service",
            "business",
            "entertainment",
        ]
        found_types = [bt for bt in expected_types if bt in business_types]
        assert len(found_types) >= 3

    @pytest.mark.asyncio
    async def test_aws_security_headers(self, client):
        """Test that proper security headers are set."""
        response = await client.get("/health")
        assert response.status_code == 200

        # Check for security headers
        headers = response.headers
        assert "x-content-type-options" in headers
        assert "x-frame-options" in headers
        assert "x-xss-protection" in headers

    @pytest.mark.asyncio
    async def test_aws_cors_configuration(self, client):
        """Test CORS configuration."""
        # Test preflight request
        response = await client.options(
            "/api/search",
            headers={
                "Origin": "https://platform.openai.com",
                "Access-Control-Request-Method": "POST",
            },
        )

        # Should allow the request (or at least not fail with CORS)
        assert response.status_code in [200, 204]

    @pytest.mark.asyncio
    async def test_aws_error_handling(self, client):
        """Test error handling on AWS."""
        # Test with invalid JSON
        response = await client.post("/api/search", content="invalid json")
        assert response.status_code == 422

        # Test with invalid pubkey
        response = await client.get("/api/profile/invalid_pubkey")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_aws_rate_limiting(self, client):
        """Test rate limiting on AWS (if configured)."""
        # This test might need adjustment based on actual rate limits
        responses = []

        for i in range(5):
            response = await client.get("/health")
            responses.append(response.status_code)

        # All requests should succeed (or we'd need to test the limit)
        assert all(status == 200 for status in responses)

    def test_aws_api_configuration_note(self):
        """Note about AWS API configuration."""
        print("\n" + "=" * 60)
        print("AWS API SERVICE TESTING NOTE")
        print("=" * 60)
        print("To run these tests against AWS:")
        print("1. Set AWS_API_SERVICE_URL environment variable")
        print("2. Set AWS_API_KEY if authentication is required")
        print("3. Ensure the API Gateway and ECS service are running")
        print("4. Run: pytest tests/test_api_service_aws.py -v")
        print("=" * 60)

        # This test always passes to document the configuration
        assert True
