"""
Local tests for the MCP Service.

These tests run against a locally started MCP service (which connects to the database service).
"""

import asyncio
import json
from typing import Any, Dict

import httpx
import pytest
import pytest_asyncio


class TestMCPServiceLocal:
    """Tests for the MCP Service running locally."""

    @pytest.fixture
    def mcp_service_url(self):
        """MCP service URL for local testing."""
        return "http://localhost:8081"

    @pytest_asyncio.fixture
    async def client(self, mcp_service_url):
        """HTTP client for MCP service."""
        async with httpx.AsyncClient(base_url=mcp_service_url, timeout=30.0) as client:
            yield client

    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """Test MCP service health endpoint."""
        response = await client.get("/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "nostr-profiles-mcp-server"
        assert "endpoints" in data

    @pytest.mark.asyncio
    async def test_mcp_initialize(self, client):
        """Test MCP initialization."""
        mcp_request = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}

        response = await client.post("/mcp", json=mcp_request)
        assert response.status_code == 200

        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert "result" in data
        assert "capabilities" in data["result"]
        assert "serverInfo" in data["result"]

    @pytest.mark.asyncio
    async def test_mcp_tools_list(self, client):
        """Test MCP tools listing."""
        mcp_request = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}

        response = await client.post("/mcp", json=mcp_request)
        assert response.status_code == 200

        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 2
        assert "result" in data
        assert "tools" in data["result"]
        assert len(data["result"]["tools"]) > 0

    @pytest.mark.asyncio
    async def test_mcp_search_profiles_tool(self, client):
        """Test MCP search_profiles tool."""
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "search_profiles",
                "arguments": {"query": "test", "limit": 5},
            },
        }

        response = await client.post("/mcp", json=mcp_request)
        assert response.status_code == 200

        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 3
        assert "result" in data
        assert "content" in data["result"]

        # Parse the content
        content_text = data["result"]["content"][0]["text"]
        content_data = json.loads(content_text)
        assert "success" in content_data
        assert "profiles" in content_data

    @pytest.mark.asyncio
    async def test_mcp_get_profile_stats_tool(self, client):
        """Test MCP get_profile_stats tool."""
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "get_profile_stats", "arguments": {}},
        }

        response = await client.post("/mcp", json=mcp_request)
        assert response.status_code == 200

        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 4

        content_text = data["result"]["content"][0]["text"]
        content_data = json.loads(content_text)
        assert "success" in content_data
        assert "stats" in content_data

    @pytest.mark.asyncio
    async def test_mcp_search_business_profiles_tool(self, client):
        """Test MCP search_business_profiles tool."""
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "search_business_profiles",
                "arguments": {
                    "query": "restaurant",
                    "business_type": "restaurant",
                    "limit": 3,
                },
            },
        }

        response = await client.post("/mcp", json=mcp_request)
        assert response.status_code == 200

        data = response.json()
        content_text = data["result"]["content"][0]["text"]
        content_data = json.loads(content_text)
        assert "success" in content_data
        assert "profiles" in content_data

    @pytest.mark.asyncio
    async def test_mcp_get_business_types_tool(self, client):
        """Test MCP get_business_types tool."""
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {"name": "get_business_types", "arguments": {}},
        }

        response = await client.post("/mcp", json=mcp_request)
        assert response.status_code == 200

        data = response.json()
        content_text = data["result"]["content"][0]["text"]
        content_data = json.loads(content_text)
        assert "success" in content_data
        assert "business_types" in content_data

    @pytest.mark.asyncio
    async def test_mcp_refresh_profiles_tool(self, client):
        """Test MCP refresh_profiles_from_nostr tool."""
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {"name": "refresh_profiles_from_nostr", "arguments": {}},
        }

        response = await client.post("/mcp", json=mcp_request)
        assert response.status_code == 200

        data = response.json()
        content_text = data["result"]["content"][0]["text"]
        content_data = json.loads(content_text)
        assert "success" in content_data

    @pytest.mark.asyncio
    async def test_mcp_unknown_tool(self, client):
        """Test MCP with unknown tool."""
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {"name": "unknown_tool", "arguments": {}},
        }

        response = await client.post("/mcp", json=mcp_request)
        assert response.status_code == 200

        data = response.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_mcp_resources_list(self, client):
        """Test MCP resources listing."""
        mcp_request = {
            "jsonrpc": "2.0",
            "id": 9,
            "method": "resources/list",
            "params": {},
        }

        response = await client.post("/mcp", json=mcp_request)
        assert response.status_code == 200

        data = response.json()
        assert "result" in data
        assert "resources" in data["result"]

    @pytest.mark.asyncio
    async def test_mcp_sse_endpoint(self, client):
        """Test MCP Server-Sent Events endpoint."""
        # Use streaming mode; do not drain entire body for an infinite SSE
        async with client.stream("GET", "/mcp/sse") as response:
            assert response.status_code == 200
            # Starlette typically returns charset parameter as well
            assert response.headers["content-type"].startswith(
                "text/event-stream"
            )
            # Optionally read a small chunk to ensure stream is alive, then stop
            async for _ in response.aiter_bytes():
                break
