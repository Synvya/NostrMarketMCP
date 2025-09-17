"""
Local tests for the Database Service.

These tests run against a locally started database service.
"""

import asyncio
import json
from typing import Any, Dict

import httpx
import pytest
import pytest_asyncio


class TestDatabaseServiceLocal:
    """Tests for the Database Service running locally."""

    @pytest.fixture
    def database_service_url(self):
        """Database service URL for local testing."""
        return "http://localhost:8082"

    @pytest_asyncio.fixture
    async def client(self, database_service_url):
        """HTTP client for database service."""
        async with httpx.AsyncClient(
            base_url=database_service_url, timeout=120.0
        ) as client:
            yield client

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """Test database service health endpoint."""
        response = await client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert "database_connected" in data
        assert "total_profiles" in data

    @pytest.mark.asyncio
    async def test_get_stats(self, client):
        """Test getting database statistics."""
        response = await client.get("/stats")
        assert response.status_code == 200

        data = response.json()
        assert "total_profiles" in data
        assert "profiles_with_name" in data
        assert "last_updated" in data

    @pytest.mark.asyncio
    async def test_search_profiles(self, client):
        """Test profile search functionality."""
        # Test basic search
        response = await client.get("/search", params={"query": "test", "limit": 10})
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "profiles" in data
        assert isinstance(data["profiles"], list)

    @pytest.mark.asyncio
    async def test_search_business_profiles(self, client):
        """Test business profile search."""
        response = await client.get(
            "/search",
            params={"query": "restaurant", "business_type": "restaurant", "limit": 5},
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "profiles" in data

    @pytest.mark.asyncio
    async def test_get_business_types(self, client):
        """Test getting available business types."""
        response = await client.get("/business-types")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "business_types" in data
        assert isinstance(data["business_types"], list)

    @pytest.mark.asyncio
    async def test_get_profile_by_pubkey(self, client):
        """Test getting a specific profile by public key."""
        # First, get some profiles to test with
        search_response = await client.get("/search", params={"query": "", "limit": 1})
        assert search_response.status_code == 200

        search_data = search_response.json()
        if search_data["profiles"]:
            # Test with an existing profile
            profile = search_data["profiles"][0]
            pubkey = profile.get("pubkey")

            if pubkey:
                response = await client.get(f"/profile/{pubkey}")
                assert response.status_code == 200

                data = response.json()
                assert data["success"] is True
                assert data["profile"] is not None

        # Test with non-existent profile
        fake_pubkey = "0" * 64
        response = await client.get(f"/profile/{fake_pubkey}")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is False
        assert data["profile"] is None

    @pytest.mark.asyncio
    async def test_manual_refresh(self, client):
        """Test manual database refresh."""
        response = await client.post("/refresh")
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert "message" in data
        assert "profiles_processed" in data
        assert "current_stats" in data

    @pytest.mark.asyncio
    async def test_pagination(self, client):
        """Test search with pagination parameters."""
        # Test with offset and limit
        response = await client.get(
            "/search", params={"query": "", "limit": 5, "offset": 0}
        )
        assert response.status_code == 200

        data = response.json()
        assert data["success"] is True
        assert len(data["profiles"]) <= 5
