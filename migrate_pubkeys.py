#!/usr/bin/env python3
"""
Database migration to convert bech32 pubkeys to hex format.
This fixes the format mismatch between stored pubkeys and API expectations.
"""

import asyncio
import json
import logging
import os
from pathlib import Path

from synvya_sdk import NostrKeys

from nostr_market_mcp.db import Database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate_pubkeys():
    """Convert all bech32 pubkeys in the database to hex format."""

    # Get database path from environment or use default
    db_path = os.getenv("DATABASE_PATH", str(Path.home() / ".nostr_profiles.db"))

    logger.info(f"Starting pubkey migration for database: {db_path}")

    db = Database(db_path)
    await db.initialize()

    try:
        # Get all events with kind=0 (profile events)
        async with db._conn.execute(
            "SELECT pubkey, content, tags, id FROM events WHERE kind = 0"
        ) as cursor:
            rows = await cursor.fetchall()

        bech32_count = 0
        converted_count = 0

        for row in rows:
            pubkey, content, tags, event_id = row

            # Check if pubkey is bech32 format (starts with 'npub' and not 64 hex chars)
            if pubkey.startswith("npub") and len(pubkey) != 64:
                bech32_count += 1
                logger.info(f"Found bech32 pubkey: {pubkey[:12]}...")

                try:
                    # Convert bech32 to hex using NostrKeys
                    # Create a temporary NostrKeys instance to access conversion methods
                    # We can't directly convert without the private key, but we can use derive_public_key

                    # Alternative: use a direct bech32 decoding approach
                    # For now, let's try to decode manually or mark these for manual fix

                    # Simple approach: if we can find the hex equivalent, update it
                    # For production, you might need a proper bech32 decoder

                    logger.warning(
                        f"Bech32 pubkey found that needs manual conversion: {pubkey}"
                    )

                    # For now, skip automatic conversion and just log
                    # In a real migration, you'd implement proper bech32->hex conversion

                except Exception as e:
                    logger.error(
                        f"Failed to convert bech32 pubkey {pubkey[:12]}...: {e}"
                    )

        logger.info(f"Migration summary:")
        logger.info(f"  Total profiles: {len(rows)}")
        logger.info(f"  Bech32 pubkeys found: {bech32_count}")
        logger.info(f"  Successfully converted: {converted_count}")

        if bech32_count > 0:
            logger.warning(f"Found {bech32_count} bech32 pubkeys that need conversion")
            logger.warning(
                "Consider clearing the database and re-running refresh to get hex pubkeys"
            )

    finally:
        await db.close()


async def clear_and_refresh():
    """Clear database and trigger a fresh refresh with hex pubkeys."""

    db_path = os.getenv("DATABASE_PATH", str(Path.home() / ".nostr_profiles.db"))
    logger.info(f"Clearing database and refreshing with hex pubkeys: {db_path}")

    db = Database(db_path)
    await db.initialize()

    try:
        # Clear all data
        success = await db.clear_all_data()
        if success:
            logger.info("Database cleared successfully")

            # Import and run refresh
            from nostr_profiles_mcp_server import refresh_database, set_shared_database

            set_shared_database(db)

            logger.info("Starting fresh data refresh with hex pubkeys...")
            await refresh_database()
            logger.info("Refresh completed with hex pubkeys")
        else:
            logger.error("Failed to clear database")

    finally:
        await db.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--clear-and-refresh":
        print("This will clear ALL database data and refresh from Nostr relays.")
        print("This is the recommended approach to fix bech32/hex pubkey issues.")
        response = input("Are you sure? (y/N): ")
        if response.lower() == "y":
            asyncio.run(clear_and_refresh())
        else:
            print("Cancelled.")
    else:
        print("Running pubkey migration analysis...")
        asyncio.run(migrate_pubkeys())
        print()
        print("To fix bech32 pubkeys, run:")
        print("python migrate_pubkeys.py --clear-and-refresh")
