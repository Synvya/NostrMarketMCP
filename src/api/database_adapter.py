#!/usr/bin/env python3
"""
Database Adapter for API Service

Provides a Database-compatible interface that uses the database client internally.
This allows existing API code to work without major changes.
"""

from typing import Any, Dict, List, Optional

from .database_client import get_database_client


class DatabaseAdapter:
    """Adapter that provides Database-compatible interface using database client."""

    def __init__(self):
        self._client = None

    async def _get_client(self):
        """Get the database client."""
        if self._client is None:
            self._client = await get_database_client()
        return self._client

    async def get_profile_stats(self) -> Dict[str, Any]:
        """Get database statistics."""
        client = await self._get_client()
        return await client.get_profile_stats()

    async def get_profile_by_pubkey(self, pubkey: str) -> Optional[Dict[str, Any]]:
        """Get a profile by public key."""
        client = await self._get_client()
        return await client.get_profile_by_pubkey(pubkey)

    async def search_profiles(
        self,
        query: str = "",
        business_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Search profiles."""
        client = await self._get_client()
        return await client.search_profiles(
            query=query, business_type=business_type, limit=limit, offset=offset
        )

    async def search_business_profiles(
        self,
        query: str = "",
        business_type: str = "",
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Search only business profiles by delegating to search with business_type filter."""
        client = await self._get_client()
        return await client.search_profiles(
            query=query, business_type=business_type, limit=limit, offset=offset
        )

    async def get_business_types(self) -> List[str]:
        """Get all business types."""
        client = await self._get_client()
        return await client.get_business_types()

    async def close(self):
        """Close the adapter (closes the underlying client)."""
        if self._client:
            await self._client.close()

    async def get_resource_data(self, resource_uri: str) -> Optional[Dict[str, Any]]:
        """Retrieve resource data by resource URI.

        Currently supports profile URIs of the form nostr://{pubkey}/profile.
        """
        client = await self._get_client()

        # Basic parsing of nostr resource URIs
        try:
            if resource_uri.startswith("nostr://"):
                parts = resource_uri.replace("nostr://", "").split("/")
                if len(parts) >= 2:
                    pubkey, resource_type = parts[0], parts[1]
                    if resource_type == "profile":
                        return await client.get_profile_by_pubkey(pubkey)
        except Exception:
            # Fall through to None
            pass

        return None


# Create a global adapter instance
_adapter = DatabaseAdapter()


async def get_database_adapter():
    """Get the database adapter instance."""
    return _adapter
