#!/usr/bin/env python3
"""
Database inspection tool for Nostr profiles database.
Shows database content in a readable format.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from nostr_market_mcp.db import Database


async def inspect_database():
    """Inspect the database and show its contents."""

    # Get database path
    db_path = os.getenv("DATABASE_PATH", "./data/nostr_profiles.db")

    if not Path(db_path).exists():
        print(f"❌ Database not found at: {db_path}")
        print("💡 Try running the container first or check the path")
        return

    print(f"🔍 Inspecting database: {db_path}")
    print("=" * 60)

    db = Database(db_path)
    await db.initialize()

    try:
        # Basic stats
        print("📊 DATABASE STATISTICS")
        print("-" * 30)

        async with db._conn.execute("SELECT COUNT(*) FROM events") as cursor:
            total_events = (await cursor.fetchone())[0]

        async with db._conn.execute(
            "SELECT COUNT(*) FROM events WHERE kind = 0"
        ) as cursor:
            profile_events = (await cursor.fetchone())[0]

        print(f"Total events: {total_events}")
        print(f"Profile events (kind=0): {profile_events}")

        # Show event kinds
        print("\n📋 EVENT KINDS")
        print("-" * 20)
        async with db._conn.execute(
            "SELECT kind, COUNT(*) as count FROM events GROUP BY kind ORDER BY kind"
        ) as cursor:
            async for row in cursor:
                kind, count = row
                kind_name = {0: "Profile", 30018: "Product"}.get(
                    kind, f"Unknown({kind})"
                )
                print(f"Kind {kind} ({kind_name}): {count} events")

        # Show sample profiles
        print("\n👥 SAMPLE PROFILES")
        print("-" * 25)
        async with db._conn.execute(
            """
            SELECT pubkey, content, tags 
            FROM events 
            WHERE kind = 0 
            ORDER BY created_at DESC 
            LIMIT 5
        """
        ) as cursor:
            i = 0
            async for row in cursor:
                i += 1
                pubkey, content, tags = row
                try:
                    profile_data = json.loads(content)
                    tags_data = json.loads(tags)

                    print(f"\n{i+1}. Profile:")
                    print(f"   Pubkey: {pubkey}")
                    print(
                        f"   Pubkey type: {'HEX' if len(pubkey) == 64 else 'BECH32' if pubkey.startswith('npub') else 'UNKNOWN'}"
                    )
                    print(f"   Name: {profile_data.get('name', 'N/A')}")
                    print(f"   About: {profile_data.get('about', 'N/A')[:50]}...")
                    print(f"   NIP05: {profile_data.get('nip05', 'N/A')}")
                    print(f"   Tags: {len(tags_data)} tags")

                    # Check if business profile
                    is_business = any(
                        tag[:2] == ["L", "business.type"]
                        for tag in tags_data
                        if len(tag) >= 2
                    )
                    business_type = None
                    for tag in tags_data:
                        if (
                            len(tag) >= 2
                            and tag[0] == "l"
                            and tag[1]
                            in [
                                "retail",
                                "restaurant",
                                "services",
                                "business",
                                "entertainment",
                                "other",
                            ]
                        ):
                            business_type = tag[1]
                            break

                    print(f"   Business: {'Yes' if is_business else 'No'}")
                    if business_type:
                        print(f"   Business Type: {business_type}")

                except json.JSONDecodeError:
                    print(f"   ❌ Invalid JSON data")

        # Show pubkey format analysis
        print("\n🔑 PUBKEY FORMAT ANALYSIS")
        print("-" * 30)

        hex_count = 0
        bech32_count = 0
        other_count = 0

        async with db._conn.execute(
            "SELECT pubkey FROM events WHERE kind = 0"
        ) as cursor:
            async for row in cursor:
                pubkey = row[0]
                if len(pubkey) == 64 and all(
                    c in "0123456789abcdef" for c in pubkey.lower()
                ):
                    hex_count += 1
                elif pubkey.startswith("npub"):
                    bech32_count += 1
                else:
                    other_count += 1

        print(f"Hex pubkeys (64 chars): {hex_count}")
        print(f"Bech32 pubkeys (npub...): {bech32_count}")
        print(f"Other formats: {other_count}")

        if bech32_count > 0:
            print("⚠️  Found bech32 pubkeys - these may cause API compatibility issues")
            print("💡 Consider running: python migrate_pubkeys.py --clear-and-refresh")

    finally:
        await db.close()


async def show_specific_profile(pubkey: str):
    """Show details for a specific profile."""

    db_path = os.getenv("DATABASE_PATH", "./data/nostr_profiles.db")
    db = Database(db_path)
    await db.initialize()

    try:
        print(f"🔍 Looking for profile: {pubkey}")
        print("=" * 60)

        async with db._conn.execute(
            """
            SELECT pubkey, content, tags, created_at 
            FROM events 
            WHERE kind = 0 AND (pubkey = ? OR pubkey LIKE ?)
        """,
            (pubkey, f"%{pubkey}%"),
        ) as cursor:
            row = await cursor.fetchone()

            if row:
                pubkey, content, tags, created_at = row
                profile_data = json.loads(content)
                tags_data = json.loads(tags)

                print(f"✅ Profile found!")
                print(f"Pubkey: {pubkey}")
                print(f"Created: {created_at}")
                print(f"Content: {json.dumps(profile_data, indent=2)}")
                print(f"Tags: {json.dumps(tags_data, indent=2)}")
            else:
                print("❌ Profile not found")

    finally:
        await db.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Show specific profile
        pubkey = sys.argv[1]
        asyncio.run(show_specific_profile(pubkey))
    else:
        # General inspection
        asyncio.run(inspect_database())
