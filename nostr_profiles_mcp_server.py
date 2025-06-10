#!/usr/bin/env python3
"""
Nostr Profiles MCP Server

A Model Context Protocol server that provides access to Nostr profile data.
This server exposes tools for searching, retrieving, and analyzing Nostr profiles.
"""

import asyncio
import json
import logging
import sys
import time
from os import getenv
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Try to import from the real SDK, fall back to mocks for testing
try:
    from synvya_sdk import (
        Namespace,
        NostrClient,
        NostrKeys,
        Profile,
        ProfileFilter,
        ProfileType,
        generate_keys,
    )
except ImportError:
    if "pytest" in sys.modules:
        from tests.mocks.synvya_sdk.nostr import NostrClient
    else:
        raise

from nostr_market_mcp.db import Database
from shared_database import get_shared_database

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default database path in user's home directory
DEFAULT_DB_PATH = Path.home() / ".nostr_profiles.db"

# Default Nostr relays to search for business profiles
DEFAULT_RELAYS = [
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://relay.snort.social",
    "wss://nostr.wine",
    "wss://relay.nostr.band",
]

NOSTR_KEY = "NOSTR_KEY"

# Get directory where the script is located
script_dir = Path(__file__).parent
# Load .env from the script's directory
load_dotenv(script_dir / ".env")
NSEC = getenv(NOSTR_KEY)
if NSEC is None:
    keys = generate_keys(NOSTR_KEY, script_dir / ".env")
else:
    keys = NostrKeys(NSEC)

# Refresh interval in seconds (5 minutes)
REFRESH_INTERVAL = 300

# Create the MCP server
app = FastMCP("Nostr Profiles")

# Global database instance
db: Optional[Database] = None

# Global refresh task
refresh_task: Optional[asyncio.Task] = None

# Global NostrClient for searching
nostr_client: Optional[NostrClient] = None


def set_shared_database(database: Database) -> None:
    """Set the shared database instance for the MCP server."""
    global db
    db = database
    logger.info("MCP server using shared database instance")


async def initialize_db():
    """Initialize the shared database connection."""
    global db
    if db is None:
        db = await get_shared_database()
        logger.info("MCP server using shared database instance")

        # Only run initial refresh and start periodic task when first creating the database
        await refresh_database()  # Initial refresh at startup
        await start_refresh_task()  # Start periodic refresh


async def cleanup_db():
    """Cleanup database connection."""
    global db

    # Stop refresh task first
    await stop_refresh_task()

    if db:
        await db.close()
        logger.info("Database connection closed")


async def ensure_db_initialized():
    """Ensure database is initialized before any operation."""
    global db
    if db is None:
        await initialize_db()


@app.tool()
async def search_profiles(query: str, limit: int = 10) -> str:
    """
    Search for Nostr profiles by content.

    Args:
        query: The search term to look for in profile content
        limit: Maximum number of results to return (default: 10)

    Returns:
        JSON string containing matching profiles
    """
    await ensure_db_initialized()
    if not db:
        return json.dumps({"error": "Database not initialized"})

    try:
        # Note: Database.search_profiles doesn't support limit parameter,
        # so we'll get all results and limit them here
        profiles = await db.search_profiles(query)
        limited_profiles = profiles[:limit]
        return json.dumps(
            {
                "success": True,
                "count": len(limited_profiles),
                "profiles": limited_profiles,
            },
            indent=2,
        )
    except Exception as e:
        logger.error(f"Error searching profiles: {e}")
        return json.dumps({"error": str(e)})


@app.tool()
async def get_profile_by_pubkey(pubkey: str) -> str:
    """
    Get a specific Nostr profile by its public key.

    Args:
        pubkey: The public key (hex string) of the profile to retrieve

    Returns:
        JSON string containing the profile data
    """
    await ensure_db_initialized()
    if not db:
        return json.dumps({"error": "Database not initialized"})

    try:
        # Use get_resource_data with profile URI
        resource_uri = f"nostr://{pubkey}/profile"
        profile = await db.get_resource_data(resource_uri)
        if profile:
            # Add pubkey to the profile data
            profile["pubkey"] = pubkey
            return json.dumps({"success": True, "profile": profile}, indent=2)
        else:
            return json.dumps({"success": False, "error": "Profile not found"})
    except Exception as e:
        logger.error(f"Error getting profile: {e}")
        return json.dumps({"error": str(e)})


@app.tool()
async def list_all_profiles(offset: int = 0, limit: int = 20) -> str:
    """
    List all profiles with pagination.

    Args:
        offset: Number of profiles to skip (default: 0)
        limit: Maximum number of profiles to return (default: 20)

    Returns:
        JSON string containing profiles and pagination info
    """
    await ensure_db_initialized()
    if not db:
        return json.dumps({"error": "Database not initialized"})

    try:
        # Note: Database.list_profiles takes (limit, offset) order
        profiles = await db.list_profiles(limit, offset)
        return json.dumps(
            {
                "success": True,
                "count": len(profiles),
                "offset": offset,
                "limit": limit,
                "profiles": profiles,
            },
            indent=2,
        )
    except Exception as e:
        logger.error(f"Error listing profiles: {e}")
        return json.dumps({"error": str(e)})


@app.tool()
async def get_profile_stats() -> str:
    """
    Get statistics about the profile database.

    Returns:
        JSON string containing database statistics
    """
    await ensure_db_initialized()
    if not db:
        return json.dumps({"error": "Database not initialized"})

    try:
        stats = await db.get_profile_stats()
        return json.dumps({"success": True, "stats": stats}, indent=2)
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return json.dumps({"error": str(e)})


@app.resource("nostr://profiles/{pubkey}")
async def get_profile_resource(pubkey: str) -> str:
    """
    Get a Nostr profile as a resource.

    Args:
        pubkey: The public key of the profile to retrieve

    Returns:
        The profile data as a formatted string
    """
    if not db:
        return "Error: Database not initialized"

    try:
        # Use get_resource_data with profile URI
        resource_uri = f"nostr://{pubkey}/profile"
        profile = await db.get_resource_data(resource_uri)
        if profile:
            # Add pubkey to the profile data
            profile["pubkey"] = pubkey
            return json.dumps(profile, indent=2)
        else:
            return "Profile not found"
    except Exception as e:
        logger.error(f"Error getting profile resource: {e}")
        return f"Error: {str(e)}"


@app.tool()
async def search_business_profiles(
    query: str = "", business_type: str = "", limit: int = 10
) -> str:
    """
    Search for business Nostr profiles with specific business type tags.

    Filters profiles that have:
    - Tag "L" with value "business.type"
    - Tag "l" with value matching business_type parameter

    Args:
        query: The search term to look for in profile content (optional)
        business_type: Business type filter - "retail", "restaurant", "services", "business", "entertainment", "other", or empty for all business types
        limit: Maximum number of results to return (default: 10)

    Returns:
        JSON string containing matching business profiles with business_type included
    """
    await ensure_db_initialized()
    if not db:
        return json.dumps({"error": "Database not initialized"})

    try:
        # Convert empty string to None for database method
        query_param = query if query else ""
        business_type_param = business_type if business_type else None

        # Get all business profiles matching criteria
        profiles = await db.search_business_profiles(query_param, business_type_param)
        limited_profiles = profiles[:limit]

        return json.dumps(
            {
                "success": True,
                "count": len(limited_profiles),
                "query": query,
                "business_type_filter": business_type or "all",
                "profiles": limited_profiles,
            },
            indent=2,
        )
    except Exception as e:
        logger.error(f"Error searching business profiles: {e}")
        return json.dumps({"error": str(e)})


@app.tool()
async def get_business_types() -> str:
    """
    Get the available business types for filtering business profiles.

    Returns:
        JSON string containing the available business type values
    """
    business_types = [
        "retail",
        "restaurant",
        "services",
        "business",
        "entertainment",
        "other",
    ]

    return json.dumps(
        {
            "success": True,
            "business_types": business_types,
            "description": "Available values for business_type parameter in search_business_profiles",
        },
        indent=2,
    )


@app.tool()
async def explain_profile_tags(tags_json: str) -> str:
    """
    Parse and explain profile tags in a human-readable format.

    Args:
        tags_json: JSON string of tags array from a profile

    Returns:
        JSON string with parsed and explained tag information
    """
    try:
        tags = json.loads(tags_json)

        explanation = {
            "success": True,
            "tag_count": len(tags),
            "parsed_tags": [],
            "business_info": {},
            "other_labels": [],
        }

        for tag in tags:
            if len(tag) >= 2:
                tag_type = tag[0]
                tag_value = tag[1]

                parsed_tag = {"type": tag_type, "value": tag_value, "description": ""}

                # Add descriptions for common tag types
                if tag_type == "L":
                    parsed_tag["description"] = f"Label namespace: {tag_value}"
                    if tag_value == "business.type":
                        explanation["business_info"]["has_business_namespace"] = True
                elif tag_type == "l":
                    parsed_tag["description"] = f"Label value: {tag_value}"
                    if tag_value in [
                        "retail",
                        "restaurant",
                        "services",
                        "business",
                        "entertainment",
                        "other",
                    ]:
                        explanation["business_info"]["business_type"] = tag_value
                        parsed_tag["description"] += f" (Business type: {tag_value})"
                    else:
                        explanation["other_labels"].append(tag_value)
                elif tag_type == "d":
                    parsed_tag["description"] = f"Event identifier: {tag_value}"
                elif tag_type == "e":
                    parsed_tag["description"] = f"Referenced event: {tag_value}"
                elif tag_type == "p":
                    parsed_tag["description"] = f"Referenced pubkey: {tag_value}"
                elif tag_type == "t":
                    parsed_tag["description"] = f"Business category: {tag_value}"
                elif tag_type == "r":
                    parsed_tag["description"] = f"Reference/URL: {tag_value}"
                else:
                    parsed_tag["description"] = (
                        f"Custom tag type '{tag_type}' with value '{tag_value}'"
                    )

                explanation["parsed_tags"].append(parsed_tag)

        # Determine if this is a business profile
        is_business = (
            explanation["business_info"].get("has_business_namespace", False)
            and "business_type" in explanation["business_info"]
        )
        explanation["is_business_profile"] = is_business

        return json.dumps(explanation, indent=2)

    except json.JSONDecodeError:
        return json.dumps({"success": False, "error": "Invalid JSON format for tags"})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})


@app.tool()
async def refresh_profiles_from_nostr() -> str:
    """
    Manually trigger a refresh of the database by searching for new business profiles from Nostr relays.

    This will search for kind:0 profiles that have the tag "L" "business.type" from the configured relays.

    Returns:
        JSON string containing the refresh result
    """
    await ensure_db_initialized()
    if not db:
        return json.dumps({"error": "Database not initialized"})

    try:
        await refresh_database()
        stats = await db.get_profile_stats()
        return json.dumps(
            {
                "success": True,
                "message": "Database refresh completed",
                "current_stats": stats,
            },
            indent=2,
        )
    except Exception as e:
        logger.error(f"Error in manual refresh: {e}")
        return json.dumps({"error": str(e)})


@app.tool()
async def get_refresh_status() -> str:
    """
    Get the status of the automatic refresh system.

    Returns:
        JSON string containing refresh configuration and status
    """
    global refresh_task, nostr_client

    status = {
        "success": True,
        "refresh_interval_seconds": REFRESH_INTERVAL,
        "refresh_interval_minutes": REFRESH_INTERVAL / 60,
        "configured_relays": DEFAULT_RELAYS,
        "refresh_task_running": refresh_task is not None and not refresh_task.done(),
        "nostr_client_connected": nostr_client is not None,
    }

    return json.dumps(status, indent=2)


@app.tool()
async def clear_database() -> str:
    """
    Clear all data from the database.

    WARNING: This will permanently delete all stored profile data.

    Returns:
        JSON string containing the operation result
    """
    await ensure_db_initialized()
    if not db:
        return json.dumps({"error": "Database not initialized"})

    try:
        success = await db.clear_all_data()
        if success:
            return json.dumps(
                {"success": True, "message": "Database cleared successfully"}, indent=2
            )
        else:
            return json.dumps(
                {"success": False, "error": "Failed to clear database"}, indent=2
            )
    except Exception as e:
        logger.error(f"Error clearing database: {e}")
        return json.dumps({"error": str(e)})


async def refresh_database():
    """Refresh the database with new Nostr profile data."""
    global nostr_client

    # Get the shared database instance
    db = await get_shared_database()
    profiles: set[Profile]

    try:
        logger.info("Refreshing database with new Nostr profile data...")

        # Connect to Nostr relays if not already connected
        if nostr_client is None:
            logger.debug(f"Connecting to relays: {DEFAULT_RELAYS}")
            try:
                nostr_client = await NostrClient.create(
                    DEFAULT_RELAYS, keys.get_private_key()
                )
                # nostr_client.set_logging_level(logging.DEBUG)
                logger.info(f"Connected to {len(DEFAULT_RELAYS)} Nostr relays")
            except Exception as e:
                logger.error(f"Failed to create NostrClient: {e}")
                logger.error(f"DEFAULT_RELAYS value: {DEFAULT_RELAYS}")
                logger.error(f"DEFAULT_RELAYS type: {type(DEFAULT_RELAYS)}")
                raise

        try:
            profile_filter = ProfileFilter(
                namespace=Namespace.BUSINESS_TYPE,
                profile_type=ProfileType.RETAIL,
            )
            profiles = await nostr_client.async_get_merchants(profile_filter)
            if profiles is not None:
                for profile in profiles:
                    logger.debug(f"Profile: {profile.to_json()}")

        except Exception as e:
            logger.error("Failed to get merchants: %s", e)
            raise

        # Store the profiles in the database
        logger.debug(f"Found {len(profiles)} business profiles to store")
        profile_count = 0

        # Update database with profile information
        for profile in profiles:
            try:
                # The Profile objects from async_get_merchants() already have identity tag parsing done
                # Get all profile fields from the populated Profile object
                profile_data = {
                    "public_key": profile.get_public_key("hex"),
                    "display_name": profile.display_name,
                    "name": profile.name,
                    "about": profile.about,
                    "picture": profile.picture,
                    "banner": profile.banner,
                    "nip05": profile.nip05,
                    "website": profile.website,
                    "email": profile.email,  # Already parsed from i-tags by synvya-sdk
                    "phone": profile.phone,  # Already parsed from i-tags by synvya-sdk
                    "street": profile.street,  # Already parsed from i-tags location by synvya-sdk
                    "city": profile.city,  # Already parsed from i-tags location by synvya-sdk
                    "state": profile.state,  # Already parsed from i-tags location by synvya-sdk
                    "zip_code": profile.zip_code,  # Already parsed from i-tags location by synvya-sdk
                    "country": profile.country,  # Already parsed from i-tags location by synvya-sdk
                    "hashtags": profile.hashtags,
                    "locations": profile.locations,
                    "bot": profile.bot,
                    "nip05_validated": profile.nip05_validated,
                    "namespace": profile.namespace,
                    "profile_type": (
                        profile.profile_type.value if profile.profile_type else None
                    ),
                    "business_type": (
                        profile.profile_type.value if profile.profile_type else None
                    ),  # Use profile_type as business_type
                    "tags": profile.tags,
                    "created_at": profile.get_created_at(),
                    "last_updated": profile.get_created_at(),
                }

                pubkey = profile_data["public_key"]
                new_created_at = profile_data["created_at"]

                # Check if profile already exists in database
                resource_uri = f"nostr://{pubkey}/profile"
                existing_profile = await db.get_resource_data(resource_uri)

                should_update = True
                if existing_profile:
                    # Get existing created_at from the database
                    existing_created_at = existing_profile.get("created_at", 0)

                    if new_created_at == existing_created_at:
                        # Same timestamp, skip update
                        should_update = False
                        logger.debug(
                            f"Skipping profile {profile.get_name()} - same created_at timestamp"
                        )
                    elif new_created_at <= existing_created_at:
                        # New profile is older or same age, skip update
                        should_update = False
                        logger.debug(
                            f"Skipping profile {profile.get_name()} - existing profile is newer"
                        )

                if should_update:
                    # Store profile data
                    result = await db.upsert_profile(resource_uri, profile_data)
                    if result:
                        profile_count += 1
                        action = "Updated" if existing_profile else "Stored"
                        logger.debug(
                            f"{action} profile for {profile.get_name()} ({pubkey[:8]}...)"
                        )
                    else:
                        logger.warning(f"Failed to store profile for {pubkey[:8]}...")
            except Exception as e:
                logger.error(
                    f"Error processing profile {profile.get_public_key('hex')[:8]}: {e}"
                )

        logger.debug(f"Successfully stored {profile_count} profiles in the database")

    except Exception as e:
        logger.error(f"Error refreshing database: {e}")


def is_business_profile(tags: List[List[str]]) -> bool:
    """Check if a profile has business.type tags indicating it's a business profile."""
    for tag in tags:
        if len(tag) >= 2 and tag[0] == "L" and tag[1] == "business.type":
            return True
    return False


async def start_refresh_task():
    """Start the periodic refresh task."""
    global refresh_task

    async def refresh_loop():
        """Periodic refresh loop."""
        while True:
            try:
                await refresh_database()
                logger.info(f"Next refresh in {REFRESH_INTERVAL} seconds")
                await asyncio.sleep(REFRESH_INTERVAL)
            except asyncio.CancelledError:
                logger.info("Refresh task cancelled")
                break
            except Exception as e:
                logger.error(f"Error in refresh loop: {e}")
                # Continue the loop after a short delay
                await asyncio.sleep(60)

    if refresh_task is None or refresh_task.done():
        refresh_task = asyncio.create_task(refresh_loop())
        logger.info(
            f"Started periodic database refresh every {REFRESH_INTERVAL} seconds"
        )


async def stop_refresh_task():
    """Stop the periodic refresh task."""
    global refresh_task, nostr_client

    if refresh_task and not refresh_task.done():
        refresh_task.cancel()
        try:
            await refresh_task
        except asyncio.CancelledError:
            pass
        refresh_task = None
        logger.info("Stopped refresh task")

    if nostr_client:
        await nostr_client.close()
        nostr_client = None
        logger.info("Closed Nostr client connection")


if __name__ == "__main__":
    # FastMCP will handle initialization, just run the server
    app.run()
