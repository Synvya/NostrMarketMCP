#!/usr/bin/env python3
"""Debug script to check database state."""

import asyncio
from pathlib import Path

from .database import Database


async def main():
    db_path = Path.home() / ".nostr_profiles.db"
    print(f"Database path: {db_path}")
    print(f"Database exists: {db_path.exists()}")
    if db_path.exists():
        print(f"Database size: {db_path.stat().st_size} bytes")

    db = Database(db_path)
    await db.initialize()

    # Check stats
    stats = await db.get_profile_stats()
    print(f"Stats: {stats}")

    # Check actual events table
    try:
        conn = db._conn
        if conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM events WHERE kind = 0")
            row = await cursor.fetchone()
            print(
                f"Actual profile count in events table: {row[0] if row else 'No data'}"
            )

            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = await cursor.fetchall()
            print(f"Tables in database: {[t[0] for t in tables]}")
        else:
            print("No database connection")
    except Exception as e:
        print(f"Error checking database: {e}")

    await db.close()


if __name__ == "__main__":
    asyncio.run(main())
