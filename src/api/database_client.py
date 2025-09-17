#!/usr/bin/env python3
"""
API-facing wrapper around the shared DatabaseClient.

Keeps the API import path stable while consolidating implementation.
"""

from typing import Optional

from pydantic import BaseModel

from src.shared.database_client import DatabaseClient as SharedDatabaseClient


class DatabaseStats(BaseModel):
    total_profiles: int
    profiles_with_name: int
    profiles_with_display_name: int
    profiles_with_about: int
    profiles_with_picture: int
    profiles_with_nip05: int
    profiles_with_website: int
    last_updated: int


# Alias to shared client for backward compatibility in API layer
class DatabaseClient(SharedDatabaseClient):
    pass


# Global client instance
_db_client: Optional[DatabaseClient] = None


async def get_database_client() -> DatabaseClient:
    global _db_client
    if _db_client is None:
        _db_client = DatabaseClient()
    return _db_client


async def close_database_client():
    global _db_client
    if _db_client:
        await _db_client.close()
        _db_client = None
