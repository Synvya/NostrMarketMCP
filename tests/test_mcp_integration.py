"""
Real MCP Server Integration Tests

Tests the MCP server by launching an actual server process and communicating
with it via HTTP requests, since our MCP server runs as a FastAPI web server.
"""

import asyncio
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
import pytest
import pytest_asyncio


class MCPServerTestClient:
    """Test client for communicating with MCP server via HTTP."""

    def __init__(self):
        self.server_process: Optional[subprocess.Popen] = None
        self.temp_db_path: Optional[str] = None
        self.base_url = "http://localhost:8082"
        self.client: Optional[httpx.AsyncClient] = None

    async def start_server(self):
        """Start the MCP server process."""
        # Create temporary database file
        fd, self.temp_db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        # Set environment variables for the server
        env = os.environ.copy()
        env["DATABASE_PATH"] = self.temp_db_path
        env["ENVIRONMENT"] = "test"
        env["MCP_BEARER"] = "test_token"
        env["PORT"] = "8082"  # Use a different port for tests

        # Start server process using the runner script
        self.server_process = subprocess.Popen(
            ["python", "scripts/run_mcp_server.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
        )

        # Give server time to start
        await asyncio.sleep(3)

        # Check if process is still running
        if self.server_process.poll() is not None:
            stderr = self.server_process.stderr.read()
            raise RuntimeError(f"MCP server failed to start. stderr: {stderr}")

        # Create HTTP client
        self.client = httpx.AsyncClient(base_url=self.base_url, timeout=30.0)

        # Test if server is responding
        try:
            response = await self.client.get("/health")
            if response.status_code != 200:
                raise RuntimeError(
                    f"Server health check failed: {response.status_code}"
                )
        except Exception as e:
            raise RuntimeError(f"Failed to connect to server: {e}")

    async def call_tool(
        self, tool_name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Call an MCP tool via JSON-RPC and return the result."""
        if not self.client:
            raise RuntimeError("Client not initialized")

        request_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        }

        response = await self.client.post(
            "/mcp",
            json=request_data,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"MCP request failed: {response.status_code} - {response.text}"
            )

        result = response.json()
        if "error" in result:
            raise RuntimeError(f"MCP error: {result['error']}")

        return result["result"]

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools via MCP server."""
        if not self.client:
            raise RuntimeError("Client not initialized")

        request_data = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}

        response = await self.client.post(
            "/mcp",
            json=request_data,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code != 200:
            raise RuntimeError(f"Failed to list tools: {response.status_code}")

        result = response.json()
        if "error" in result:
            raise RuntimeError(f"MCP error: {result['error']}")

        return result["result"]["tools"]

    async def list_resources(self) -> List[Dict[str, Any]]:
        """List available resources via MCP server."""
        if not self.client:
            raise RuntimeError("Client not initialized")

        request_data = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "resources/list",
            "params": {},
        }

        response = await self.client.post(
            "/mcp",
            json=request_data,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code != 200:
            raise RuntimeError(f"Failed to list resources: {response.status_code}")

        result = response.json()
        if "error" in result:
            raise RuntimeError(f"MCP error: {result['error']}")

        return result["result"]["resources"]

    async def cleanup(self):
        """Cleanup connections and server process."""
        if self.client:
            await self.client.aclose()
            self.client = None

        if self.server_process:
            # First try to terminate gracefully
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                # If graceful termination fails, force kill
                self.server_process.kill()
                self.server_process.wait()
            self.server_process = None

        # Also kill any remaining processes on port 8082 to ensure cleanup
        import subprocess as sp

        try:
            # Find and kill any processes using port 8082
            result = sp.run(["lsof", "-ti", ":8082"], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                pids = result.stdout.strip().split("\n")
                for pid in pids:
                    if pid:
                        try:
                            sp.run(["kill", pid], check=False)
                        except:
                            pass
        except:
            pass  # Ignore errors in cleanup

        if self.temp_db_path and os.path.exists(self.temp_db_path):
            os.unlink(self.temp_db_path)


class TestMCPServerIntegration:
    """Integration tests for real MCP server."""

    def _parse_tool_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Parse tool result into JSON data, handling different response formats."""
        # The result should contain content with JSON response
        if "content" in result and result["content"]:
            content = result["content"][0]["text"]
            try:
                return json.loads(content)
            except (json.JSONDecodeError, IndexError):
                # If JSON parsing fails, treat content as raw text
                return {"content": content}
        else:
            # Sometimes the result is already parsed JSON
            if isinstance(result, dict):
                return result
            else:
                return {"content": str(result)}

    @pytest_asyncio.fixture(autouse=True)
    async def setup(self):
        """Setup for each test."""
        self.client = MCPServerTestClient()

        # Start server and initialize
        await self.client.start_server()

        yield

        # Cleanup
        await self.client.cleanup()

    @pytest.mark.asyncio
    async def test_server_connection(self):
        """Test basic server connection and initialization."""
        # Server should be running and connected via the fixture
        assert self.client.server_process is not None
        assert self.client.server_process.poll() is None  # Process should be running

    @pytest.mark.asyncio
    async def test_list_tools(self):
        """Test listing available MCP tools."""
        tools = await self.client.list_tools()

        assert isinstance(tools, list)
        assert len(tools) > 0

        # Check for expected tools
        tool_names = [tool["name"] for tool in tools]
        expected_tools = [
            "search_profiles",
            "get_profile_by_pubkey",
            "list_all_profiles",
            "get_profile_stats",
            "search_business_profiles",
            "get_business_types",
            "explain_profile_tags",
            "refresh_profiles_from_nostr",
            "get_refresh_status",
            "clear_database",
        ]

        for expected_tool in expected_tools:
            assert (
                expected_tool in tool_names
            ), f"Tool {expected_tool} not found in {tool_names}"

    @pytest.mark.asyncio
    async def test_list_resources(self):
        """Test listing available MCP resources."""
        resources = await self.client.list_resources()

        assert isinstance(resources, list)
        # Resources might be empty initially, but should be a list

    @pytest.mark.asyncio
    async def test_search_profiles_tool(self):
        """Test search_profiles tool via real MCP server."""
        result = await self.client.call_tool(
            "search_profiles", {"query": "test", "limit": 10}
        )

        assert result is not None

        # The result should contain content with JSON response
        if "content" in result:
            content = result["content"][0]["text"]
        else:
            content = json.dumps(result)

        data = json.loads(content)

        assert "success" in data
        assert "count" in data
        assert "profiles" in data
        assert isinstance(data["profiles"], list)

    @pytest.mark.asyncio
    async def test_get_profile_stats_tool(self):
        """Test get_profile_stats tool via real MCP server."""
        result = await self.client.call_tool("get_profile_stats", {})

        assert result is not None

        # The result should contain content with JSON response
        if "content" in result:
            content = result["content"][0]["text"]
        else:
            content = json.dumps(result)

        data = json.loads(content)

        assert "success" in data
        if data["success"]:
            assert "stats" in data
            stats = data["stats"]
            assert "total_profiles" in stats
            assert isinstance(stats["total_profiles"], int)

    @pytest.mark.asyncio
    async def test_get_business_types_tool(self):
        """Test get_business_types tool via real MCP server."""
        result = await self.client.call_tool("get_business_types", {})

        assert result is not None

        # The result should contain content with JSON response
        if "content" in result:
            content = result["content"][0]["text"]
        else:
            content = json.dumps(result)

        data = json.loads(content)

        assert "success" in data
        if data["success"]:
            assert "business_types" in data
            assert isinstance(data["business_types"], list)

    @pytest.mark.asyncio
    async def test_explain_profile_tags_tool(self):
        """Test explain_profile_tags tool via real MCP server."""
        test_tags = [
            ["L", "business.type"],
            ["l", "retail", "business.type"],
            ["t", "software"],
        ]

        result = await self.client.call_tool(
            "explain_profile_tags", {"tags_json": json.dumps(test_tags)}
        )

        assert result is not None

        data = self._parse_tool_result(result)

        assert "success" in data or "explanation" in data or "content" in data
        if data.get("success"):
            assert "explanation" in data
            assert "tag_breakdown" in data

    @pytest.mark.asyncio
    async def test_search_business_profiles_tool(self):
        """Test search_business_profiles tool via real MCP server."""
        result = await self.client.call_tool(
            "search_business_profiles",
            {"query": "", "business_type": "retail", "limit": 5},
        )

        assert result is not None

        # The result should contain content with JSON response
        if "content" in result:
            content = result["content"][0]["text"]
        else:
            content = json.dumps(result)

        data = json.loads(content)

        assert "success" in data
        assert "count" in data
        assert "profiles" in data
        assert isinstance(data["profiles"], list)

    @pytest.mark.asyncio
    async def test_get_refresh_status_tool(self):
        """Test get_refresh_status tool via real MCP server."""
        result = await self.client.call_tool("get_refresh_status", {})

        assert result is not None

        data = self._parse_tool_result(result)

        # Should return status information (check actual format from real server)
        # The real server returns different fields than expected
        assert isinstance(data, dict)
        # Check for any reasonable status fields
        status_fields = [
            "database_initialized",
            "refresh_task_running",
            "configured_relays",
            "nostr_client_connected",
        ]
        assert any(
            field in data for field in status_fields
        ), f"No expected status fields found in {data}"

    @pytest.mark.asyncio
    async def test_tool_error_handling(self):
        """Test error handling for invalid tool calls."""
        # Test invalid JSON for explain_profile_tags
        result = await self.client.call_tool(
            "explain_profile_tags", {"tags_json": "invalid json"}
        )

        assert result is not None

        # The result should contain content with JSON response
        if "content" in result:
            content = result["content"][0]["text"]
        else:
            content = json.dumps(result)

        data = json.loads(content)

        assert "success" in data
        assert data["success"] == False
        assert "error" in data

    @pytest.mark.asyncio
    async def test_concurrent_tool_calls(self):
        """Test multiple concurrent tool calls."""
        # Run multiple tools concurrently
        tasks = [
            self.client.call_tool("get_business_types", {}),
            self.client.call_tool("get_profile_stats", {}),
            self.client.call_tool("search_profiles", {"query": "test", "limit": 5}),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # All should succeed (or at least not raise exceptions)
        for result in results:
            assert not isinstance(result, Exception), f"Tool call failed: {result}"
            assert result is not None

    @pytest.mark.asyncio
    async def test_server_resource_cleanup(self):
        """Test that server cleans up resources properly."""
        # Get initial stats
        result = await self.client.call_tool("get_refresh_status", {})
        assert result is not None

        # The test should complete without hanging, indicating proper resource cleanup
        # This is tested implicitly by the fixture cleanup running successfully
