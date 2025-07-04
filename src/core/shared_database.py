#!/usr/bin/env python3
"""
Shared database instance for both API and MCP servers.
Ensures both servers use the exact same database connection.
"""
import logging
import os
from pathlib import Path
from typing import Optional

from .database import Database

logger = logging.getLogger(__name__)

# Default database path - respect DATABASE_PATH environment variable
DEFAULT_DB_PATH = Path(
    os.getenv("DATABASE_PATH", str(Path.home() / ".nostr_profiles.db"))
)

# Global shared database instance
_shared_db: Optional[Database] = None


async def get_shared_database(db_path: Optional[Path] = None) -> Database:
    """Get the shared database instance, creating it if necessary.

    Args:
        db_path: Optional custom database path. If None, uses DEFAULT_DB_PATH.

    Returns:
        Database: The shared database instance
    """
    global _shared_db

    if _shared_db is None:
        path = db_path or DEFAULT_DB_PATH
        _shared_db = Database(path)
        await _shared_db.initialize()
        logger.info(f"Shared database initialized at {path}")

    return _shared_db


def set_shared_database(database: Database) -> None:
    """Set the shared database instance.

    This is useful for testing or when you want to use a specific database instance
    across multiple modules.

    Args:
        database: The Database instance to use as the shared database
    """
    global _shared_db
    _shared_db = database
    logger.info("Shared database instance set")


async def close_shared_database():
    """Close the shared database connection."""
    global _shared_db

    if _shared_db:
        await _shared_db.close()
        _shared_db = None
        logger.info("Shared database closed")


def is_database_initialized() -> bool:
    """Check if the shared database is initialized."""
    return _shared_db is not None
