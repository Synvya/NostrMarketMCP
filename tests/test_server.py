"""Tests for the MCP server module."""

import json
import sys
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Import from the real mcp package
from mcp import Resource, Tool
from mcp.server import FastMCP

from nostr_market_mcp.db import Database
from nostr_market_mcp.server import MCPBridge, create_mcp_app


class MockDatabase:
    """Mock database for testing."""

    def __init__(self) -> None:
        self.get_resource_data = AsyncMock()
        self.search_products = AsyncMock()

        # Set default responses
        self.get_resource_data.return_value = {"name": "Test Resource"}
        self.search_products.return_value = [{"id": "prod1", "name": "Test Product"}]


@pytest.fixture
def mcp_app_and_bridge():
    """Create a FastAPI app and MCP bridge with mocks."""
    app = FastAPI()
    db = MockDatabase()

    # Patch the FastMCP to avoid actual SSE connections
    with patch("nostr_market_mcp.server.FastMCP") as mock_fastmcp:
        # Mock the FastMCP instance
        mock_fastmcp_instance = mock_fastmcp.return_value
        mock_fastmcp_instance.list_resources = MagicMock()
        mock_fastmcp_instance.read_resource = MagicMock()
        mock_fastmcp_instance.tool = MagicMock()
        mock_fastmcp_instance.sse_app = MagicMock()

        # Create the bridge
        bridge = MCPBridge(db, app)

        # Create a test client
        client = TestClient(app)

        yield app, bridge, client


@pytest.mark.asyncio
async def test_create_mcp_app():
    """Test creating a FastAPI app with MCP bridge."""
    # Use the real implementation for this test
    app = FastAPI()
    db = MockDatabase()

    # Patch the FastMCP class to avoid actual registration
    with patch("nostr_market_mcp.server.FastMCP") as mock_fastmcp:
        mock_instance = mock_fastmcp.return_value
        mock_instance.sse_app = MagicMock()

        app, bridge = create_mcp_app(db)

        # Verify app was created with expected title
        assert app.title == "NostrMarketMCP"

        # Verify FastMCP was created and attached
        mock_fastmcp.assert_called_once()
        mock_instance.sse_app.assert_called_once_with(app)


@pytest.mark.asyncio
async def test_resource_decorators(mcp_app_and_bridge):
    """Test the resource decorators."""
    _, bridge, _ = mcp_app_and_bridge

    # Get the list_resources decorator function
    list_resources_decorator = bridge.mcp_server.list_resources

    # Check that it was called correctly
    list_resources_decorator.assert_called_once()


@pytest.mark.asyncio
async def test_tool_decorator(mcp_app_and_bridge):
    """Test the tool decorator."""
    _, bridge, _ = mcp_app_and_bridge

    # Get the tool decorator function
    tool_decorator = bridge.mcp_server.tool

    # Check that it was called with the correct name and description
    tool_decorator.assert_called_once()
    args, kwargs = tool_decorator.call_args
    assert kwargs["name"] == "search_products"
    assert kwargs["description"] == "Search for products by keyword"
    assert "param_schema" in kwargs  # Just check that the param_schema was included


@pytest.mark.asyncio
async def test_notify_resource_update(mcp_app_and_bridge):
    """Test notifying clients about resource updates."""
    _, bridge, _ = mcp_app_and_bridge

    # Call the method
    await bridge.notify_resource_update(
        "nostr://test/profile", {"name": "Updated Resource"}
    )

    # This is mostly just testing that the method doesn't raise exceptions
    # The actual notification logic is handled by FastMCP internally
