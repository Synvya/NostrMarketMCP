"""
API Integration Tests for Nostr Profiles API.

IMPORTANT: These tests require manual server startup due to FastAPI TestClient complexity.

To run these tests:
1. Start the API server manually:
   python scripts/run_api_server.py

2. Run the tests:
   pytest tests/test_api_integration.py -v

The MCP tests (test_mcp_*.py) provide comprehensive coverage without requiring manual setup.
"""

import asyncio
import os
import tempfile
from pathlib import Path

import httpx
import pytest
import pytest_asyncio


class TestAPIWithManualServer:
    """API tests that require manual server startup."""

    def test_manual_testing_required(self):
        """Test that explains manual testing requirement."""
        print("\n" + "=" * 60)
        print("API INTEGRATION TESTING INSTRUCTIONS")
        print("=" * 60)
        print("1. Start the server manually:")
        print("   python scripts/run_api_server.py")
        print()
        print("2. Run API tests against the running server:")
        print("   pytest tests/test_api_integration.py::TestLiveAPIEndpoints -v")
        print()
        print("3. For automated testing, use MCP tests:")
        print("   pytest tests/test_mcp_*.py -v")
        print("=" * 60)

        # This test always passes to document the requirement
        assert True


class TestLiveAPIEndpoints:
    """Tests that run against a manually started API server."""

    def setup_method(self):
        """Setup for API tests - assumes server is running on default port."""
        self.base_url = "http://127.0.0.1:8080"
        self.api_key = os.getenv("API_KEY", "local_test_api_key")
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key,
        }

    def test_health_check(self):
        """Test health endpoint (no auth required)."""
        try:
            response = httpx.get(f"{self.base_url}/health", timeout=5.0)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "secure-nostr-profiles-api"
            print(f"✅ Health check passed: {data['status']}")
        except httpx.ConnectError:
            pytest.skip(
                "Server not running. Start with: python scripts/run_api_server.py"
            )

    def test_search_profiles(self):
        """Test search profiles endpoint."""
        try:
            payload = {"query": "test", "limit": 5}
            response = httpx.post(
                f"{self.base_url}/api/search",
                headers=self.headers,
                json=payload,
                timeout=10.0,
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
            assert "profiles" in data
            print(f"✅ Search returned {data['count']} profiles")
        except httpx.ConnectError:
            pytest.skip(
                "Server not running. Start with: python scripts/run_api_server.py"
            )

    def test_get_stats(self):
        """Test stats endpoint."""
        try:
            response = httpx.get(
                f"{self.base_url}/api/stats", headers=self.headers, timeout=10.0
            )
            assert response.status_code == 200
            data = response.json()
            assert data["success"] == True
            assert "stats" in data
            print(f"✅ Stats: {data['stats']['total_profiles']} total profiles")
        except httpx.ConnectError:
            pytest.skip(
                "Server not running. Start with: python scripts/run_api_server.py"
            )


if __name__ == "__main__":
    # Run the manual instructions test by default
    pytest.main([__file__ + "::TestAPIWithManualServer", "-v", "-s"])
