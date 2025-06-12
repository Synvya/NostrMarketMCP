"""
Comprehensive MCP Server tests for Nostr Profiles MCP Server.

Tests all MCP tools and resources with proper database mocking,
error handling, and response validation.
"""

import asyncio
import json
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest
import pytest_asyncio

# Import the MCP server and its dependencies
import nostr_profiles_mcp_server


class MockDatabase:
    """Mock database for testing MCP server functionality."""

    def __init__(self):
        self.profiles = [
            {
                "pubkey": "57d03534460df449321cde3757b1b379a8377bace8199101df0716e20dbb7991",
                "name": "test",
                "display_name": "Test Unit",
                "about": "Testing for the sake of testing...",
                "picture": "https://blossom.band/650ccd2a489b3717566a67bbabbbf32f28f2b458d39a3f155d998a00f2aab8a8",
                "website": "https://www.synvya.com",
                "nip05": "test@synvya.com",
                "business_type": "retail",
                "namespace": "business.type",
                "tags": [
                    ["L", "business.type"],
                    ["l", "retail", "business.type"],
                    ["t", "software"],
                ],
                "created_at": 1749574818,
            }
        ]

    async def search_profiles(self, query: str) -> List[Dict]:
        """Mock profile search."""
        return [p for p in self.profiles if query.lower() in json.dumps(p).lower()]

    async def get_resource_data(self, resource_uri: str) -> Dict:
        """Mock resource data retrieval."""
        if "profile" in resource_uri:
            pubkey = resource_uri.split("/")[-2]
            for profile in self.profiles:
                if profile["pubkey"] == pubkey:
                    return profile
        return None

    async def get_all_profiles(self, offset: int = 0, limit: int = 20) -> List[Dict]:
        """Mock get all profiles."""
        return self.profiles[offset : offset + limit]

    async def list_profiles(self, limit: int = 20, offset: int = 0) -> List[Dict]:
        """Mock list profiles with (limit, offset) parameter order."""
        return self.profiles[offset : offset + limit]

    async def get_profile_stats(self) -> Dict:
        """Mock profile statistics."""
        return {
            "total_profiles": len(self.profiles),
            "profiles_with_name": sum(1 for p in self.profiles if p.get("name")),
            "profiles_with_display_name": sum(
                1 for p in self.profiles if p.get("display_name")
            ),
            "profiles_with_about": sum(1 for p in self.profiles if p.get("about")),
            "profiles_with_picture": sum(1 for p in self.profiles if p.get("picture")),
            "profiles_with_nip05": sum(1 for p in self.profiles if p.get("nip05")),
            "profiles_with_website": sum(1 for p in self.profiles if p.get("website")),
            "last_updated": 1749574818,
        }

    async def search_business_profiles(
        self, query: str = "", business_type: str = ""
    ) -> List[Dict]:
        """Mock business profile search."""
        results = self.profiles.copy()
        if query:
            results = [p for p in results if query.lower() in json.dumps(p).lower()]
        if business_type:
            results = [p for p in results if p.get("business_type") == business_type]
        return results

    async def get_business_types(self) -> List[str]:
        """Mock get business types."""
        return ["retail", "restaurant", "service", "business", "entertainment", "other"]

    async def clear_all_data(self) -> bool:
        """Mock clear all data."""
        self.profiles.clear()
        return True

    async def upsert_profile(self, profile_data: Dict) -> bool:
        """Mock upsert profile."""
        return True

    async def close(self) -> None:
        """Mock database close."""
        pass


class TestMCPServer:
    """Test suite for MCP server tools and resources."""

    @pytest_asyncio.fixture(autouse=True)
    async def setup(self):
        """Setup for each test."""
        self.mock_db = MockDatabase()

        # Set the mock database
        nostr_profiles_mcp_server.set_shared_database(self.mock_db)
        nostr_profiles_mcp_server.db = self.mock_db

        yield

        # Cleanup - patch the cleanup to avoid NostrClient close issues
        with patch(
            "nostr_profiles_mcp_server.stop_refresh_task", new_callable=AsyncMock
        ) as mock_stop:
            mock_stop.return_value = None
            await nostr_profiles_mcp_server.cleanup_db()

    # Profile Tools Tests
    @pytest.mark.asyncio
    async def test_search_profiles_success(self):
        """Test search_profiles tool with valid query."""
        result = await nostr_profiles_mcp_server.search_profiles("test", 10)
        data = json.loads(result)

        assert data["success"] == True
        assert "count" in data
        assert "profiles" in data
        assert data["count"] >= 0
        assert isinstance(data["profiles"], list)

    @pytest.mark.asyncio
    async def test_search_profiles_no_results(self):
        """Test search_profiles with query that returns no results."""
        result = await nostr_profiles_mcp_server.search_profiles("nonexistent", 10)
        data = json.loads(result)

        assert data["success"] == True
        assert data["count"] == 0
        assert data["profiles"] == []

    @pytest.mark.asyncio
    async def test_get_profile_by_pubkey_success(self):
        """Test get_profile_by_pubkey with valid pubkey."""
        pubkey = "57d03534460df449321cde3757b1b379a8377bace8199101df0716e20dbb7991"
        result = await nostr_profiles_mcp_server.get_profile_by_pubkey(pubkey)
        data = json.loads(result)

        assert data["success"] == True
        assert "profile" in data
        assert data["profile"]["pubkey"] == pubkey

    @pytest.mark.asyncio
    async def test_get_profile_by_pubkey_not_found(self):
        """Test get_profile_by_pubkey with non-existent pubkey."""
        pubkey = "nonexistent_pubkey"
        result = await nostr_profiles_mcp_server.get_profile_by_pubkey(pubkey)
        data = json.loads(result)

        assert data["success"] == False
        assert "error" in data
        assert "not found" in data["error"].lower()

    @pytest.mark.asyncio
    async def test_list_all_profiles(self):
        """Test list_all_profiles tool."""
        result = await nostr_profiles_mcp_server.list_all_profiles(0, 20)
        data = json.loads(result)

        assert data["success"] == True
        assert "profiles" in data
        assert "count" in data
        assert "offset" in data
        assert "limit" in data
        assert isinstance(data["profiles"], list)

    @pytest.mark.asyncio
    async def test_get_profile_stats(self):
        """Test get_profile_stats tool."""
        result = await nostr_profiles_mcp_server.get_profile_stats()
        data = json.loads(result)

        assert data["success"] == True
        assert "stats" in data
        stats = data["stats"]

        required_fields = [
            "total_profiles",
            "profiles_with_name",
            "profiles_with_display_name",
            "profiles_with_about",
            "profiles_with_picture",
            "profiles_with_nip05",
            "profiles_with_website",
        ]

        for field in required_fields:
            assert field in stats
            assert isinstance(stats[field], int)

    @pytest.mark.asyncio
    async def test_search_business_profiles(self):
        """Test search_business_profiles tool."""
        result = await nostr_profiles_mcp_server.search_business_profiles(
            "", "retail", 10
        )
        data = json.loads(result)

        assert data["success"] == True
        assert "count" in data
        assert "profiles" in data
        assert isinstance(data["profiles"], list)

    @pytest.mark.asyncio
    async def test_get_business_types(self):
        """Test get_business_types tool."""
        result = await nostr_profiles_mcp_server.get_business_types()
        data = json.loads(result)

        assert data["success"] == True
        assert "business_types" in data
        assert isinstance(data["business_types"], list)
        assert len(data["business_types"]) > 0

    @pytest.mark.asyncio
    async def test_explain_profile_tags(self):
        """Test explain_profile_tags tool."""
        tags_json = json.dumps(
            [["L", "business.type"], ["l", "retail", "business.type"]]
        )
        result = await nostr_profiles_mcp_server.explain_profile_tags(tags_json)
        data = json.loads(result)

        assert data["success"] == True
        assert "tag_count" in data
        assert "parsed_tags" in data
        assert "business_info" in data
        assert isinstance(data["parsed_tags"], list)

    @pytest.mark.asyncio
    async def test_explain_profile_tags_invalid_json(self):
        """Test explain_profile_tags with invalid JSON."""
        result = await nostr_profiles_mcp_server.explain_profile_tags("invalid json")
        data = json.loads(result)

        assert data["success"] == False
        assert "error" in data

    # Utility Tools Tests
    @pytest.mark.asyncio
    async def test_refresh_profiles_from_nostr(self):
        """Test refresh_profiles_from_nostr tool."""
        with patch(
            "nostr_profiles_mcp_server.refresh_database", new_callable=AsyncMock
        ) as mock_refresh:
            mock_refresh.return_value = None
            result = await nostr_profiles_mcp_server.refresh_profiles_from_nostr()
            data = json.loads(result)

            assert data["success"] == True
            assert "message" in data
            mock_refresh.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_refresh_status(self):
        """Test get_refresh_status tool."""
        result = await nostr_profiles_mcp_server.get_refresh_status()
        data = json.loads(result)

        assert data["success"] == True
        assert "refresh_interval_seconds" in data
        assert "configured_relays" in data
        assert "refresh_task_running" in data
        assert isinstance(data["configured_relays"], list)

    @pytest.mark.asyncio
    async def test_clear_database(self):
        """Test clear_database tool."""
        result = await nostr_profiles_mcp_server.clear_database()
        data = json.loads(result)

        assert data["success"] == True
        assert "message" in data

        # Error Handling Tests

    @pytest.mark.asyncio
    async def test_tools_without_database(self):
        """Test tools behavior when database is not initialized."""
        # Mock ensure_db_initialized to do nothing and clear the database reference
        with patch(
            "nostr_profiles_mcp_server.ensure_db_initialized", new_callable=AsyncMock
        ) as mock_ensure:
            mock_ensure.return_value = None
            nostr_profiles_mcp_server.db = None

            result = await nostr_profiles_mcp_server.search_profiles("test")
            data = json.loads(result)
            assert "error" in data
            assert "not initialized" in data["error"].lower()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
