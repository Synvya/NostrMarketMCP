"""
AWS tests for the MCP Service.

These tests run against the MCP service deployed on AWS.
"""

import asyncio
import json
import os
from typing import Any, Dict

import httpx
import pytest
import pytest_asyncio


class TestMCPServiceAWS:
    """Tests for the MCP Service running on AWS."""

    @pytest.fixture
    def mcp_service_url(self):
        """MCP service URL for AWS testing."""
        # This would be the internal AWS MCP service URL
        base_url = os.getenv("AWS_MCP_SERVICE_URL", "http://nostr-mcp:8081")
        return base_url

    @pytest_asyncio.fixture
    async def client(self, mcp_service_url):
        """HTTP client for MCP service."""
        async with httpx.AsyncClient(base_url=mcp_service_url, timeout=60.0) as client:
            yield client

    @pytest.mark.asyncio
    async def test_aws_health_check(self, client):
        """Test MCP service health endpoint on AWS."""
        try:
            response = await client.get("/health")
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "healthy"
            assert data["service"] == "nostr-profiles-mcp-server"
            assert "endpoints" in data
        except httpx.ConnectError:
            pytest.skip("MCP service not accessible (internal service)")

    @pytest.mark.asyncio
    async def test_aws_mcp_with_real_data(self, client):
        """Test MCP tools with real AWS data."""
        try:
            # Test search_profiles tool
            mcp_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {
                    "name": "search_profiles",
                    "arguments": {"query": "restaurant", "limit": 10},
                },
            }

            response = await client.post("/mcp", json=mcp_request)
            assert response.status_code == 200

            data = response.json()
            content_text = data["result"]["content"][0]["text"]
            content_data = json.loads(content_text)

            assert content_data["success"] is True
            # Should have real results
            assert len(content_data["profiles"]) > 0
        except httpx.ConnectError:
            pytest.skip("MCP service not accessible (internal service)")

    @pytest.mark.asyncio
    async def test_aws_mcp_performance(self, client):
        """Test MCP performance on AWS."""
        try:
            import time

            mcp_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "get_profile_stats", "arguments": {}},
            }

            start_time = time.time()
            response = await client.post("/mcp", json=mcp_request)
            end_time = time.time()

            assert response.status_code == 200
            # Should respond quickly
            assert (end_time - start_time) < 5.0

            data = response.json()
            content_text = data["result"]["content"][0]["text"]
            content_data = json.loads(content_text)

            assert content_data["success"] is True
            stats = content_data["stats"]
            assert stats["total_profiles"] > 0
        except httpx.ConnectError:
            pytest.skip("MCP service not accessible (internal service)")

    @pytest.mark.asyncio
    async def test_aws_mcp_business_search(self, client):
        """Test MCP business search with AWS data."""
        try:
            mcp_request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "search_business_profiles",
                    "arguments": {
                        "query": "coffee",
                        "business_type": "restaurant",
                        "limit": 5,
                    },
                },
            }

            response = await client.post("/mcp", json=mcp_request)
            assert response.status_code == 200

            data = response.json()
            content_text = data["result"]["content"][0]["text"]
            content_data = json.loads(content_text)

            assert content_data["success"] is True
            assert "profiles" in content_data
        except httpx.ConnectError:
            pytest.skip("MCP service not accessible (internal service)")

    @pytest.mark.asyncio
    async def test_aws_mcp_refresh_capability(self, client):
        """Test MCP refresh capability on AWS."""
        try:
            mcp_request = {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "refresh_profiles_from_nostr", "arguments": {}},
            }

            response = await client.post("/mcp", json=mcp_request)
            assert response.status_code == 200

            data = response.json()
            content_text = data["result"]["content"][0]["text"]
            content_data = json.loads(content_text)

            # Refresh should work (though may take time)
            assert content_data["success"] is True
        except httpx.ConnectError:
            pytest.skip("MCP service not accessible (internal service)")

    @pytest.mark.asyncio
    async def test_aws_mcp_all_tools_available(self, client):
        """Test that all MCP tools are available on AWS."""
        try:
            mcp_request = {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/list",
                "params": {},
            }

            response = await client.post("/mcp", json=mcp_request)
            assert response.status_code == 200

            data = response.json()
            tools = data["result"]["tools"]

            expected_tools = [
                "search_profiles",
                "get_profile_by_pubkey",
                "search_business_profiles",
                "get_profile_stats",
                "refresh_profiles_from_nostr",
                "list_all_profiles",
                "get_business_types",
            ]

            tool_names = [tool["name"] for tool in tools]
            for expected_tool in expected_tools:
                assert expected_tool in tool_names
        except httpx.ConnectError:
            pytest.skip("MCP service not accessible (internal service)")

    @pytest.mark.asyncio
    async def test_aws_mcp_error_handling(self, client):
        """Test MCP error handling on AWS."""
        try:
            # Test with invalid tool
            mcp_request = {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {"name": "nonexistent_tool", "arguments": {}},
            }

            response = await client.post("/mcp", json=mcp_request)
            assert response.status_code == 200

            data = response.json()
            assert "error" in data
        except httpx.ConnectError:
            pytest.skip("MCP service not accessible (internal service)")

    @pytest.mark.asyncio
    async def test_aws_mcp_sse_functionality(self, client):
        """Test MCP SSE functionality on AWS."""
        try:
            response = await client.get("/mcp/sse")
            assert response.status_code == 200
            assert "text/event-stream" in response.headers.get("content-type", "")
        except httpx.ConnectError:
            pytest.skip("MCP service not accessible (internal service)")

    def test_aws_mcp_architecture_note(self):
        """Note about AWS MCP service architecture."""
        print("\n" + "=" * 60)
        print("AWS MCP SERVICE TESTING NOTE")
        print("=" * 60)
        print("The MCP service runs as an internal ECS service and")
        print("communicates with the database service within the VPC.")
        print("To test against AWS:")
        print("1. Set AWS_MCP_SERVICE_URL environment variable")
        print("2. Ensure you're testing from within the VPC")
        print("3. Run: pytest tests/test_mcp_service_aws.py -v")
        print("=" * 60)

        # This test always passes to document the architecture
        assert True
