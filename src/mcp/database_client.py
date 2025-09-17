#!/usr/bin/env python3
"""
MCP-facing wrapper around the shared DatabaseClient.

Keeps the MCP import path stable while consolidating implementation.
"""

from typing import Optional

from src.shared.database_client import DatabaseClient as SharedDatabaseClient


class MCPDatabaseClient(SharedDatabaseClient):
    pass


# Global client instance for MCP service
_mcp_db_client: Optional[MCPDatabaseClient] = None


async def get_mcp_database_client() -> MCPDatabaseClient:
    global _mcp_db_client
    if _mcp_db_client is None:
        _mcp_db_client = MCPDatabaseClient()
    return _mcp_db_client


async def close_mcp_database_client():
    global _mcp_db_client
    if _mcp_db_client:
        await _mcp_db_client.close()
        _mcp_db_client = None
