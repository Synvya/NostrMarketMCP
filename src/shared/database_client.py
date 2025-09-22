#!/usr/bin/env python3
"""
Shared Database Client

HTTP client used by both the API service and the MCP service to talk to the
Database Service (single source of truth).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger(__name__)


def _default_base_url() -> str:
    return os.getenv("DATABASE_SERVICE_URL", "http://nostr-database:8082").rstrip("/")


class DatabaseClient:
    """HTTP client for the Database Service.

    Methods provide a stable interface consumed by API and MCP layers.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        *,
        total_timeout: float = 30.0,
        connect_timeout: float = 5.0,
        refresh_timeout: float = 120.0,
    ):
        self.base_url = (base_url or _default_base_url()).rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None
        self._timeouts = {
            "total": float(total_timeout),
            "connect": float(connect_timeout),
            "refresh": float(refresh_timeout),
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(
                total=self._timeouts["total"], connect=self._timeouts["connect"]
            )
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    # ---- Service endpoints ----
    async def health_check(self) -> Dict[str, Any]:
        session = await self._get_session()
        try:
            async with session.get(f"{self.base_url}/health") as response:
                if response.status == 200:
                    return await response.json()
                raise Exception(f"Database service health check failed: {response.status}")
        except Exception as e:
            logger.error(f"Database service health check failed: {e}")
            raise

    async def get_profile_stats(self) -> Dict[str, Any]:
        session = await self._get_session()
        try:
            async with session.get(f"{self.base_url}/stats") as response:
                if response.status == 200:
                    return await response.json()
                raise Exception(f"Failed to get stats: {response.status}")
        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            raise

    async def get_profile_by_pubkey(self, pubkey: str) -> Optional[Dict[str, Any]]:
        session = await self._get_session()
        try:
            async with session.get(f"{self.base_url}/profile/{pubkey}") as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("profile")
                if response.status == 404:
                    return None
                raise Exception(f"Failed to get profile: {response.status}")
        except Exception as e:
            logger.error(f"Failed to get profile {pubkey}: {e}")
            raise

    async def search_profiles(
        self,
        *,
        query: str = "",
        business_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        session = await self._get_session()
        params = {"query": query, "limit": limit, "offset": offset}
        if business_type:
            params["business_type"] = business_type
        try:
            async with session.get(
                f"{self.base_url}/search", params=params
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("profiles", [])
                raise Exception(f"Search failed: {response.status}")
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    async def get_business_types(self) -> List[str]:
        session = await self._get_session()
        try:
            async with session.get(f"{self.base_url}/business-types") as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("business_types", [])
                raise Exception(f"Failed to get business types: {response.status}")
        except Exception as e:
            logger.error(f"Failed to get business types: {e}")
            raise

    async def trigger_refresh(self) -> Dict[str, Any]:
        session = await self._get_session()
        try:
            async with session.post(
                f"{self.base_url}/refresh",
                timeout=aiohttp.ClientTimeout(
                    total=self._timeouts["refresh"], connect=self._timeouts["connect"]
                ),
            ) as response:
                if response.status == 200:
                    return await response.json()
                raise Exception(f"Refresh failed: {response.status}")
        except Exception as e:
            logger.error(f"Manual refresh failed: {e}")
            raise

