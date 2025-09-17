#!/usr/bin/env python3
"""
Shared database instance for both API and MCP servers.
Ensures both servers use the exact same database connection.
"""
import logging
import os
import sys
from pathlib import Path
from typing import Optional

from .database import Database

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
    if "pytest" in sys.modules or os.getenv("ENVIRONMENT") == "test":
        from tests.mocks.synvya_sdk.nostr import NostrClient
    else:
        raise

logger = logging.getLogger(__name__)

# Default database path - respect DATABASE_PATH environment variable
DEFAULT_DB_PATH = Path(
    os.getenv("DATABASE_PATH", str(Path.home() / ".nostr_profiles.db"))
)

# Default Nostr relays for data fetching
DEFAULT_RELAYS = [
    "wss://relay.damus.io",
    "wss://nos.lol",
    "wss://relay.snort.social",
    "wss://nostr.wine",
    "wss://relay.nostr.band",
]

# Global shared database instance
_shared_db: Optional[Database] = None

# Global nostr client for data fetching
_nostr_client: Optional[NostrClient] = None


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


async def cleanup_shared_database():
    """Cleanup shared database resources."""
    await close_shared_database()


def _get_nostr_keys() -> NostrKeys:
    """Get or create Nostr keys for data fetching."""
    from dotenv import load_dotenv

    # Get directory where the script is located
    script_dir = Path(__file__).parent
    # Load .env from the script's directory
    load_dotenv(script_dir / ".env")

    NOSTR_KEY = "NOSTR_KEY"
    NSEC = os.getenv(NOSTR_KEY)
    if NSEC is None:
        return generate_keys(NOSTR_KEY, script_dir / ".env")
    else:
        return NostrKeys(NSEC)


async def initialize_shared_database(db_path: Optional[Path] = None):
    """Initialize the shared database connection.

    Args:
        db_path: Optional custom database path
    """
    # Get the shared database instance - this will create it if it doesn't exist
    await get_shared_database(db_path)
    logger.info("Shared database initialized")


async def refresh_shared_database():
    """Refresh the shared database with new Nostr profile data."""
    global _nostr_client

    # Get the shared database instance
    db = await get_shared_database()
    all_profiles: set[Profile] = set()

    try:
        logger.info("Refreshing database with new Nostr profile data...")

        # Connect to Nostr relays if not already connected
        if _nostr_client is None:
            logger.debug(f"Connecting to relays: {DEFAULT_RELAYS}")
            try:
                keys = _get_nostr_keys()
                _nostr_client = await NostrClient.create(
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
                profiles = await _nostr_client.async_get_merchants(profile_filter)
                if profiles is not None:
                    all_profiles.update(profiles)
                    logger.debug(
                        f"Found {len(profiles)} {business_type.value} profiles"
                    )
                    for profile in profiles:
                        logger.debug(f"Profile: {profile.to_json()}")

            # Process and store all profiles
            profile_count = 0
            logger.info(f"Processing {len(all_profiles)} unique profiles...")

            for profile in all_profiles:
                try:
                    # Get public key in hex format
                    pubkey = profile.get_public_key("hex")

                    # Check if profile already exists
                    existing_profile = await db.get_profile_by_pubkey(pubkey)

                    # Create profile data
                    profile_data = {
                        "pubkey": pubkey,
                        "name": profile.get_name(),
                        "display_name": profile.get_display_name(),
                        "about": profile.get_about(),
                        "picture": profile.get_picture(),
                        "banner": profile.get_banner(),
                        "website": profile.get_website(),
                        "nip05": profile.get_nip05(),
                        "lud16": profile.get_lud16(),
                        "profile_type": (
                            profile.get_profile_type().value
                            if profile.get_profile_type()
                            else None
                        ),
                        "business_type": (
                            profile.get_business_type().value
                            if profile.get_business_type()
                            else None
                        ),
                        "business_hours": profile.get_business_hours(),
                        "location": profile.get_location(),
                        "tags": profile.get_tags(),
                        "is_merchant": True,  # All profiles from merchant search are merchants
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
                        result = await db.upsert_profile(profile_data)
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
                        f"Error processing profile {profile.get_public_key('hex')[:8]}: {e}"
                    )

            logger.info(
                f"Database refresh completed: processed {profile_count} profiles"
            )

        except Exception as e:
            logger.error(f"Error during profile search: {e}")

    except Exception as e:
        logger.error(f"Error refreshing database: {e}")
        raise


def is_database_initialized() -> bool:
    """Check if the shared database is initialized."""
    return _shared_db is not None
