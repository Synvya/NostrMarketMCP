#!/usr/bin/env python3
from __future__ import annotations
"""
Nostr Profiles Database Service

A dedicated service for managing the Nostr profiles database.
Handles data ingestion, refresh, and provides HTTP API for data access.
"""

import asyncio
import json
import logging
import os
import sys
import time
from contextlib import asynccontextmanager
from os import getenv
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Import the real SDK explicitly; fail fast if unavailable
from synvya_sdk import NostrClient, generate_keys
from synvya_sdk.models import (
    Namespace,
    NostrKeys,
    Profile,
    ProfileFilter,
    ProfileType,
)

from .database import Database

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Default Nostr relays for data fetching
DEFAULT_RELAYS = [
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://relay.snort.social",
    "wss://nostr.wine",
    "wss://relay.nostr.band",
]

# Default database path - respect DATABASE_PATH environment variable
DEFAULT_DB_PATH = Path(os.getenv("DATABASE_PATH", "/app/data/nostr_profiles.db"))

# Refresh interval in seconds (1 hour)
REFRESH_INTERVAL = 3600

# NOSTR key configuration
NOSTR_KEY = "NOSTR_KEY"

# Global variables
database: Optional[Database] = None
nostr_client: Optional[NostrClient] = None
refresh_task: Optional[asyncio.Task] = None


# Pydantic models for API responses
class DatabaseStats(BaseModel):
    total_profiles: int
    profiles_with_name: int
    profiles_with_display_name: int
    profiles_with_about: int
    profiles_with_picture: int
    profiles_with_nip05: int
    profiles_with_website: int
    last_updated: int


class HealthResponse(BaseModel):
    status: str
    database_connected: bool
    total_profiles: int
    last_refresh: Optional[int]
    next_refresh: Optional[int]


class RefreshResponse(BaseModel):
    success: bool
    message: str
    profiles_processed: int
    current_stats: DatabaseStats


class ProfileResponse(BaseModel):
    success: bool
    profile: Optional[Dict[str, Any]]
    message: str


class SearchResponse(BaseModel):
    success: bool
    profiles: List[Dict[str, Any]]
    total_count: int
    message: str


def _get_nostr_keys() -> NostrKeys:
    """Get or create Nostr keys for data fetching."""
    # Get directory where the script is located
    script_dir = Path(__file__).parent.parent.parent
    # Load .env from the project root
    load_dotenv(script_dir / ".env")

    NSEC = os.getenv(NOSTR_KEY)
    if NSEC is None:
        return generate_keys(NOSTR_KEY, script_dir / ".env")
    else:
        return NostrKeys(NSEC)


async def initialize_database():
    """Initialize the database connection."""
    global database

    if database is None:
        database = Database(DEFAULT_DB_PATH)
        await database.initialize()
        logger.info(f"Database initialized at {DEFAULT_DB_PATH}")

    return database


async def refresh_database() -> int:
    """Refresh the database with new Nostr profile data."""
    global nostr_client, database

    if database is None:
        await initialize_database()

    all_profiles: set[Profile] = set()
    profile_count = 0

    try:
        logger.info("Starting database refresh with new Nostr profile data...")

        # Connect to Nostr relays if not already connected
        if nostr_client is None:
            logger.debug(f"Connecting to relays: {DEFAULT_RELAYS}")
            try:
                keys = _get_nostr_keys()
                nostr_client = await NostrClient.create(
                    DEFAULT_RELAYS, keys.get_private_key()
                )
                logger.info(f"Connected to {len(DEFAULT_RELAYS)} Nostr relays")
            except Exception as e:
                logger.error(f"Failed to create NostrClient: {e}")
                raise

        # Define all business types to search for
        business_types = [
            ProfileType.RETAIL,
            ProfileType.RESTAURANT,
            ProfileType.SERVICE,
            ProfileType.BUSINESS,
            ProfileType.ENTERTAINMENT,
            ProfileType.OTHER,
        ]

        try:
            # Search for profiles with each business type
            for business_type in business_types:
                logger.debug(f"Searching for {business_type.value} profiles...")
                profile_filter = ProfileFilter(
                    namespace=Namespace.BUSINESS_TYPE,
                    profile_type=business_type,
                )
                profiles = await nostr_client.async_get_merchants(profile_filter)
                if profiles is not None:
                    all_profiles.update(profiles)
                    logger.debug(
                        f"Found {len(profiles)} {business_type.value} profiles"
                    )

            logger.info(f"Found {len(all_profiles)} unique profiles to process")

            # Process and store all profiles
            for profile in all_profiles:
                try:
                    # Get public key in hex format
                    pubkey = profile.get_public_key("hex")

                    # Check if profile already exists
                    resource_uri = f"nostr://{pubkey}/profile"
                    existing_profile = await database.get_resource_data(resource_uri)

                    # Create profile data
                    profile_data = {
                        # Required for upsert_profile
                        "public_key": pubkey,
                        # Core fields present in the SDK
                        "name": profile.get_name(),
                        "display_name": profile.get_display_name(),
                        "about": profile.get_about(),
                        "picture": profile.get_picture(),
                        "banner": profile.get_banner(),
                        "website": profile.get_website(),
                        "nip05": profile.get_nip05(),
                        "profile_type": (
                            profile.get_profile_type().value
                            if profile.get_profile_type()
                            else None
                        ),
                        # Additional available fields
                        "created_at": profile.get_created_at(),
                        "email": profile.get_email(),
                        "phone": profile.get_phone(),
                        "profile_url": profile.get_profile_url(),
                        "namespace": profile.get_namespace(),
                        "city": profile.get_city(),
                        "state": profile.get_state(),
                        "country": profile.get_country(),
                        "street": profile.get_street(),
                        "zip_code": profile.get_zip_code(),
                        "hashtags": profile.get_hashtags() or [],
                        "locations": list(profile.get_locations() or []),
                        "environment": profile.get_environment(),
                        "nip05_validated": profile.is_nip05_validated(),
                        "bot": profile.is_bot(),
                        # Legacy/optional fields not in current SDK: store as empty values
                        "lud16": "",
                        # Computed/derived fields handled by DB layer via tags, not here:
                        # - business_type
                    }

                    # Determine if we should update
                    should_update = True
                    if existing_profile:
                        # Update logic: check if any significant fields changed
                        fields_to_check = [
                            "name",
                            "display_name",
                            "about",
                            "picture",
                            "website",
                            "nip05",
                            "lud16",
                        ]
                        should_update = any(
                            profile_data.get(field) != existing_profile.get(field)
                            for field in fields_to_check
                        )

                    if should_update:
                        # Store profile data
                        result = await database.upsert_profile(profile_data)
                        if result:
                            profile_count += 1
                            action = "Updated" if existing_profile else "Stored"
                            logger.debug(
                                f"{action} profile for {profile.get_name()} ({pubkey[:8]}...)"
                            )
                        else:
                            logger.warning(
                                f"Failed to store profile for {pubkey[:8]}..."
                            )
                except Exception as e:
                    logger.error(
                        f"Error processing profile {profile.get_public_key('hex')[:8] if hasattr(profile, 'get_public_key') else 'unknown'}: {e}"
                    )

            logger.info(
                f"Database refresh completed: processed {profile_count} profiles"
            )

        except Exception as e:
            logger.error(f"Error during profile search: {e}")
            raise

    except Exception as e:
        logger.error(f"Error refreshing database: {e}")
        raise

    return profile_count


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
        try:
            # Try to close if the method exists
            if hasattr(nostr_client, "close"):
                await nostr_client.close()
            elif hasattr(nostr_client, "disconnect"):
                await nostr_client.disconnect()
            # If no close method, just set to None
        except Exception as e:
            logger.warning(f"Error closing Nostr client: {e}")
        finally:
            nostr_client = None
            logger.info("Closed Nostr client connection")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app."""
    # Startup
    logger.info("Starting Nostr Profiles Database Service")

    await initialize_database()

    # Skip network operations in test environment
    if getenv("ENVIRONMENT") != "test":
        # Initial refresh at startup
        try:
            await refresh_database()
            logger.info("Initial database refresh completed")
        except Exception as e:
            logger.warning(f"Initial refresh failed: {e}")

        # Start periodic refresh task
        await start_refresh_task()

    yield

    # Shutdown
    logger.info("Shutting down Nostr Profiles Database Service")
    await stop_refresh_task()

    if database:
        await database.close()


# Create the FastAPI app
app = FastAPI(
    title="Nostr Profiles Database Service",
    description="Dedicated service for managing Nostr profile data",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API Endpoints


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    if database is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    try:
        stats = await database.get_profile_stats()

        return HealthResponse(
            status="healthy",
            database_connected=True,
            total_profiles=stats.get("total_profiles", 0),
            last_refresh=stats.get("last_updated"),
            next_refresh=int(time.time()) + REFRESH_INTERVAL if refresh_task else None,
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=503, detail=f"Database health check failed: {e}"
        )


@app.get("/stats", response_model=DatabaseStats)
async def get_database_stats():
    """Get database statistics."""
    if database is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    try:
        stats = await database.get_profile_stats()
        return DatabaseStats(**stats)
    except Exception as e:
        logger.error(f"Failed to get database stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {e}")


@app.post("/refresh", response_model=RefreshResponse)
async def manual_refresh():
    """Manually trigger a database refresh."""
    if database is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    try:
        logger.info("Manual refresh triggered")
        # In test environment, avoid long-running network operations
        if getenv("ENVIRONMENT") == "test":
            logger.info("Test environment detected - performing quick refresh (skipped)")
            stats = await database.get_profile_stats()
            return RefreshResponse(
                success=True,
                message="Test refresh skipped",
                profiles_processed=0,
                current_stats=DatabaseStats(**stats),
            )

        profiles_processed = await refresh_database()
        stats = await database.get_profile_stats()

        return RefreshResponse(
            success=True,
            message=f"Database refresh completed successfully",
            profiles_processed=profiles_processed,
            current_stats=DatabaseStats(**stats),
        )
    except Exception as e:
        logger.error(f"Manual refresh failed: {e}")
        raise HTTPException(status_code=500, detail=f"Refresh failed: {e}")


@app.get("/profile/{pubkey}", response_model=ProfileResponse)
async def get_profile(pubkey: str):
    """Get a specific profile by public key."""
    if database is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    try:
        resource_uri = f"nostr://{pubkey}/profile"
        profile = await database.get_resource_data(resource_uri)

        if profile:
            return ProfileResponse(
                success=True, profile=profile, message="Profile found"
            )
        else:
            return ProfileResponse(
                success=False, profile=None, message="Profile not found"
            )
    except Exception as e:
        logger.error(f"Failed to get profile {pubkey}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get profile: {e}")


@app.get("/search", response_model=SearchResponse)
async def search_profiles(
    query: str = "",
    business_type: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """Search profiles by query and/or business type."""
    if database is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    try:
        if business_type:
            profiles = await database.search_business_profiles(query, business_type)
        else:
            profiles = await database.search_profiles(query)

        # Apply limit and offset manually since the Database methods don't support them
        start = offset
        end = offset + limit
        profiles = profiles[start:end]

        return SearchResponse(
            success=True,
            profiles=profiles,
            total_count=len(profiles),
            message=f"Found {len(profiles)} profiles",
        )
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")


@app.get("/business-types")
async def get_business_types():
    """Get all available business types."""
    if database is None:
        raise HTTPException(status_code=503, detail="Database not initialized")

    try:
        business_types = await database.get_business_types()
        return {"success": True, "business_types": business_types}
    except Exception as e:
        logger.error(f"Failed to get business types: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get business types: {e}"
        )


if __name__ == "__main__":
    import uvicorn

    host = getenv("HOST", "0.0.0.0")
    port = int(getenv("PORT", "8082"))

    # Only auto-run the server when explicitly allowed.
    # Prevents accidental double-starts during tests/tools that import this module.
    if getenv("RUN_STANDALONE", "1") == "1":
        logger.info(f"Starting Database Service on http://{host}:{port}")
        uvicorn.run(app, host=host, port=port)
