"""Database module for NostrMarketMCP.

Provides a thin wrapper for SQLite with helpers for event storage and resource querying.
"""

import hashlib
import json
import logging
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, cast

import aiosqlite

logger = logging.getLogger(__name__)

# SQL statements for database setup and operations
SQL_CREATE_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS events (
    id TEXT NOT NULL,
    pubkey TEXT NOT NULL,
    kind INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    d_tag TEXT,
    tags TEXT NOT NULL,
    PRIMARY KEY (kind, pubkey, d_tag)
)
"""

SQL_INSERT_EVENT = """
INSERT INTO events (id, pubkey, kind, content, created_at, d_tag, tags)
VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (kind, pubkey, d_tag)
DO UPDATE SET 
    id = CASE WHEN events.created_at < ? THEN ? ELSE events.id END,
    content = CASE WHEN events.created_at < ? THEN ? ELSE events.content END,
    created_at = CASE WHEN events.created_at < ? THEN ? ELSE events.created_at END,
    tags = CASE WHEN events.created_at < ? THEN ? ELSE events.tags END
WHERE d_tag IS NOT NULL
"""

SQL_INSERT_EVENT_NO_D_TAG = """
INSERT OR REPLACE INTO events (id, pubkey, kind, content, created_at, d_tag, tags)
VALUES (?, ?, ?, ?, ?, NULL, ?)
"""

SQL_GET_PROFILE = """
SELECT content FROM events 
WHERE kind = 0 AND pubkey = ? 
ORDER BY created_at DESC LIMIT 1
"""

SQL_GET_CATALOG = """
SELECT id, content, d_tag, created_at FROM events
WHERE kind = 30018 AND pubkey = ?
ORDER BY created_at DESC
"""

SQL_GET_PRODUCT = """
SELECT content FROM events
WHERE kind = 30018 AND pubkey = ? AND d_tag = ?
"""

SQL_GET_STALLS = """
SELECT id, content, d_tag, created_at FROM events
WHERE kind = 30017 AND pubkey = ?
ORDER BY created_at DESC
"""

SQL_GET_STALL = """
SELECT content FROM events
WHERE kind = 30017 AND pubkey = ? AND d_tag = ?
"""

SQL_GET_ALL_STALLS = """
SELECT pubkey, content, d_tag, created_at, tags FROM events
WHERE kind = 30017
ORDER BY created_at DESC
"""

SQL_GET_ALL_PRODUCTS = """
SELECT pubkey, content, d_tag, created_at, tags FROM events
WHERE kind = 30018
ORDER BY created_at DESC
"""


class DatabaseError(Exception):
    """Exception raised for database errors."""

    pass


class Database:
    """Thin wrapper for SQLite database with helper methods."""

    def __init__(self, db_path: Union[str, Path]) -> None:
        """Initialize the database with the given path.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        self._conn: Optional[aiosqlite.Connection] = None

    async def initialize(self) -> None:
        """Initialize the database connection and create tables if needed."""
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = await aiosqlite.connect(self.db_path)
        await self._conn.execute(SQL_CREATE_EVENTS_TABLE)
        await self._conn.commit()
        logger.info(f"Database initialized at {self.db_path}")

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None
            logger.info("Database connection closed")

    async def upsert_event(
        self,
        id: str,
        pubkey: str,
        kind: int,
        content: str,
        created_at: int,
        tags: List[List[str]],
    ) -> bool:
        """Insert or update an event in the database.

        Uses the replaceable event logic: kind+pubkey+d_tag is the primary key,
        and we keep the event with the highest created_at.

        Args:
            id: Event ID
            pubkey: Event pubkey
            kind: Event kind
            content: Event content
            created_at: Event timestamp
            tags: Event tags

        Returns:
            bool: True if the event was inserted or updated, False otherwise

        Raises:
            DatabaseError: If the database connection is not initialized
        """
        if not self._conn:
            raise DatabaseError("Database not initialized")

        # Extract d-tag if it exists
        d_tag = None
        for tag in tags:
            if len(tag) >= 2 and tag[0] == "d":
                d_tag = tag[1]
                break

        tags_json = json.dumps(tags)

        try:
            if d_tag:
                # Use replaceable event logic with d-tag
                await self._conn.execute(
                    SQL_INSERT_EVENT,
                    (
                        id,
                        pubkey,
                        kind,
                        content,
                        created_at,
                        d_tag,
                        tags_json,
                        created_at,
                        id,
                        created_at,
                        content,
                        created_at,
                        created_at,
                        created_at,
                        tags_json,
                    ),
                )
            else:
                # For events without d-tag, just replace based on kind+pubkey
                await self._conn.execute(
                    SQL_INSERT_EVENT_NO_D_TAG,
                    (id, pubkey, kind, content, created_at, tags_json),
                )

            await self._conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Database error when upserting event: {e}")
            return False

    async def get_resource_data(self, resource_uri: str) -> Optional[Dict[str, Any]]:
        """Get resource data for the given URI.

        Args:
            resource_uri: URI in the format nostr://{npub}/profile,
                          nostr://{npub}/catalog, or nostr://{npub}/product/{d}

        Returns:
            Optional[Dict[str, Any]]: Resource data or None if not found

        Raises:
            DatabaseError: If the database connection is not initialized
        """
        if not self._conn:
            raise DatabaseError("Database not initialized")

        # Parse the resource URI
        parts = resource_uri.replace("nostr://", "").split("/")
        if len(parts) < 2:
            logger.error(f"Invalid resource URI: {resource_uri}")
            return None

        pubkey = parts[0]
        resource_type = parts[1]

        try:
            if resource_type == "profile":
                # Get merchant profile with created_at timestamp and tags for business_type
                async with self._conn.execute(
                    "SELECT content, created_at, tags FROM events WHERE kind = 0 AND pubkey = ? ORDER BY created_at DESC LIMIT 1",
                    (pubkey,),
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return None
                    profile_data = json.loads(row[0])
                    profile_data["created_at"] = row[
                        1
                    ]  # Add created_at to the profile data

                    # Extract business_type from tags if present
                    if row[2]:  # Check if tags exist
                        tags = json.loads(row[2])
                        business_type = None
                        for tag in tags:
                            if (
                                len(tag) >= 2
                                and tag[0] == "l"
                                and tag[1]
                                in [
                                    "retail",  # ProfileType.RETAIL
                                    "restaurant",  # ProfileType.RESTAURANT
                                    "service",  # ProfileType.SERVICE
                                    "business",  # ProfileType.BUSINESS
                                    "entertainment",  # ProfileType.ENTERTAINMENT
                                    "other",  # ProfileType.OTHER
                                ]
                            ):
                                business_type = tag[1]
                                break
                        profile_data["business_type"] = business_type

                    return profile_data

            elif resource_type == "catalog":
                # Get product catalog
                products = []
                async with self._conn.execute(SQL_GET_CATALOG, (pubkey,)) as cursor:
                    async for row in cursor:
                        product_data = json.loads(row[1])
                        products.append(product_data)
                return {"products": products}

            elif resource_type == "product" and len(parts) >= 3:
                # Get specific product
                d_tag = parts[2]
                async with self._conn.execute(
                    SQL_GET_PRODUCT, (pubkey, d_tag)
                ) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return None
                    return json.loads(row[0])

            elif resource_type == "stalls":
                # Get stall catalog for a merchant
                stalls = []
                async with self._conn.execute(SQL_GET_STALLS, (pubkey,)) as cursor:
                    async for row in cursor:
                        stall_data = json.loads(row[1])
                        stall_data["d_tag"] = row[2]
                        stall_data["created_at"] = row[3]
                        stalls.append(stall_data)
                return {"stalls": stalls}

            elif resource_type == "stall" and len(parts) >= 3:
                # Get specific stall
                d_tag = parts[2]
                async with self._conn.execute(SQL_GET_STALL, (pubkey, d_tag)) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return None
                    return json.loads(row[0])
            else:
                logger.error(f"Unknown resource type: {resource_type}")
                return None

        except (sqlite3.Error, json.JSONDecodeError) as e:
            logger.error(f"Error retrieving resource data: {e}")
            return None

    async def get_resource_rows(
        self, kind: int, pubkey: str, d_tag: Optional[str] = None
    ) -> List[Tuple[str, str, int, str]]:
        """Get event rows for the specified kind, pubkey, and optional d-tag.

        Args:
            kind: Event kind
            pubkey: Event pubkey
            d_tag: Optional d-tag for filtering

        Returns:
            List[Tuple[str, str, int, str]]: List of (id, content, created_at, tags) tuples

        Raises:
            DatabaseError: If the database connection is not initialized
        """
        if not self._conn:
            raise DatabaseError("Database not initialized")

        try:
            if d_tag:
                query = """
                SELECT id, content, created_at, tags FROM events
                WHERE kind = ? AND pubkey = ? AND d_tag = ?
                ORDER BY created_at DESC
                """
                params = (kind, pubkey, d_tag)
            else:
                query = """
                SELECT id, content, created_at, tags FROM events
                WHERE kind = ? AND pubkey = ?
                ORDER BY created_at DESC
                """
                params = (kind, pubkey)

            results: List[Tuple[str, str, int, str]] = []
            async with self._conn.execute(query, params) as cursor:
                async for row in cursor:
                    results.append(cast(Tuple[str, str, int, str], row))
            return results
        except sqlite3.Error as e:
            logger.error(f"Database error when getting resource rows: {e}")
            return []

    async def search_products(
        self, query: str, pubkey: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for products matching the query.

        Args:
            query: Search query string
            pubkey: Optional pubkey to restrict search to a specific merchant

        Returns:
            List[Dict[str, Any]]: List of matching product data

        Raises:
            DatabaseError: If the database connection is not initialized
        """
        if not self._conn:
            raise DatabaseError("Database not initialized")

        try:
            # Convert query to lowercase for case-insensitive search
            query = query.lower()

            # Build the SQL query based on whether a pubkey is provided
            if pubkey:
                sql = """
                SELECT pubkey, content, d_tag, created_at, tags FROM events
                WHERE kind = 30018 AND pubkey = ?
                ORDER BY created_at DESC
                """
                params = (pubkey,)
            else:
                sql = SQL_GET_ALL_PRODUCTS
                params = ()

            results = []
            async with self._conn.execute(sql, params) as cursor:
                async for row in cursor:
                    try:
                        product_pubkey = row[0]
                        product_data = json.loads(row[1])
                        d_tag = row[2]
                        created_at = row[3]
                        tags = json.loads(row[4])

                        # Check if product matches search query
                        product_name = str(product_data.get("name", "")).lower()
                        product_desc = str(product_data.get("description", "")).lower()

                        if query in product_name or query in product_desc:
                            product_data["pubkey"] = product_pubkey
                            product_data["d_tag"] = d_tag
                            product_data["created_at"] = created_at
                            product_data["tags"] = tags
                            results.append(product_data)
                    except json.JSONDecodeError:
                        pass  # Skip invalid JSON

            return results
        except sqlite3.Error as e:
            logger.error(f"Database error when searching products: {e}")
            return []

    async def list_products(
        self, limit: int = 10, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List all products with pagination.

        Args:
            limit: Maximum number of products to return
            offset: Number of products to skip

        Returns:
            List[Dict[str, Any]]: List of product data with pubkey and metadata included

        Raises:
            DatabaseError: If the database connection is not initialized
        """
        if not self._conn:
            raise DatabaseError("Database not initialized")

        try:
            sql = """
            SELECT pubkey, content, d_tag, created_at, tags FROM events
            WHERE kind = 30018
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """

            results = []
            async with self._conn.execute(sql, (limit, offset)) as cursor:
                async for row in cursor:
                    try:
                        product_pubkey = row[0]
                        product_data = json.loads(row[1])
                        d_tag = row[2]
                        created_at = row[3]
                        tags = json.loads(row[4])

                        product_data["pubkey"] = product_pubkey
                        product_data["d_tag"] = d_tag
                        product_data["created_at"] = created_at
                        product_data["tags"] = tags
                        results.append(product_data)
                    except json.JSONDecodeError:
                        pass  # Skip invalid JSON

            return results
        except sqlite3.Error as e:
            logger.error(f"Database error when listing products: {e}")
            return []

    async def get_product_by_pubkey_and_dtag(
        self, pubkey: str, d_tag: str
    ) -> Optional[Dict[str, Any]]:
        """Get a specific product by pubkey and d-tag.

        Args:
            pubkey: Product owner's pubkey
            d_tag: Product identifier (d-tag)

        Returns:
            Optional[Dict[str, Any]]: Product data or None if not found

        Raises:
            DatabaseError: If the database connection is not initialized
        """
        if not self._conn:
            raise DatabaseError("Database not initialized")

        try:
            async with self._conn.execute(
                """
                SELECT content, created_at, tags FROM events
                WHERE kind = 30018 AND pubkey = ? AND d_tag = ?
                """,
                (pubkey, d_tag),
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None

                product_data = json.loads(row[0])
                product_data["pubkey"] = pubkey
                product_data["d_tag"] = d_tag
                product_data["created_at"] = row[1]
                product_data["tags"] = json.loads(row[2])
                return product_data

        except (sqlite3.Error, json.JSONDecodeError) as e:
            logger.error(f"Database error when getting product: {e}")
            return None

    async def get_product_stats(self) -> Dict[str, Any]:
        """Get statistics about products in the database.

        Returns:
            Dict[str, Any]: Dictionary containing product statistics

        Raises:
            DatabaseError: If the database connection is not initialized
        """
        if not self._conn:
            raise DatabaseError("Database not initialized")

        try:
            stats = {}

            # Total products
            async with self._conn.execute(
                "SELECT COUNT(*) FROM events WHERE kind = 30018"
            ) as cursor:
                result = await cursor.fetchone()
                stats["total_products"] = result[0] if result else 0

            # Products by merchant
            async with self._conn.execute(
                """
                SELECT COUNT(DISTINCT pubkey) FROM events WHERE kind = 30018
                """
            ) as cursor:
                result = await cursor.fetchone()
                stats["unique_merchants"] = result[0] if result else 0

            # Most recent product
            async with self._conn.execute(
                """
                SELECT created_at FROM events WHERE kind = 30018
                ORDER BY created_at DESC LIMIT 1
                """
            ) as cursor:
                result = await cursor.fetchone()
                stats["latest_product_timestamp"] = result[0] if result else None

            return stats
        except sqlite3.Error as e:
            logger.error(f"Database error when getting product stats: {e}")
            return {}

    async def search_profiles(self, query: str) -> List[Dict[str, Any]]:
        """Search for profiles matching the query.

        Args:
            query: Search query string

        Returns:
            List[Dict[str, Any]]: List of matching profile data with pubkey and tags included

        Raises:
            DatabaseError: If the database connection is not initialized
        """
        if not self._conn:
            raise DatabaseError("Database not initialized")

        try:
            # Convert query to lowercase for case-insensitive search
            query = query.lower()

            # Split query into individual terms (handle commas, spaces, etc.)
            query_terms = [
                term.strip() for term in re.split(r"[,\s]+", query) if term.strip()
            ]

            sql = """
            SELECT pubkey, content, tags FROM events
            WHERE kind = 0
            ORDER BY created_at DESC
            """

            results = []
            async with self._conn.execute(sql) as cursor:
                async for row in cursor:
                    try:
                        pubkey = row[0]
                        profile_data = json.loads(row[1])
                        tags = json.loads(row[2])

                        # Check if profile matches search query
                        name = str(profile_data.get("name", "")).lower()
                        display_name = str(profile_data.get("display_name", "")).lower()
                        about = str(profile_data.get("about", "")).lower()
                        nip05 = str(profile_data.get("nip05", "")).lower()

                        # Search in location and address fields
                        country = str(profile_data.get("country", "")).lower()
                        city = str(profile_data.get("city", "")).lower()
                        state = str(profile_data.get("state", "")).lower()
                        zip_code = str(profile_data.get("zip_code", "")).lower()
                        street = str(profile_data.get("street", "")).lower()

                        # Search in hashtags (convert array to searchable string)
                        hashtags = profile_data.get("hashtags", [])
                        hashtags_text = " ".join(
                            str(tag).lower() for tag in hashtags if tag
                        )

                        # Also search in Nostr event tags (specifically "t" tags for hashtags)
                        event_hashtags = []
                        for tag in tags:
                            if len(tag) >= 2 and tag[0] == "t":
                                event_hashtags.append(str(tag[1]).lower())
                        event_hashtags_text = " ".join(event_hashtags)

                        # Create searchable text by combining all fields
                        searchable_text = " ".join(
                            [
                                name,
                                display_name,
                                about,
                                nip05,
                                country,
                                city,
                                state,
                                zip_code,
                                street,
                                hashtags_text,
                                event_hashtags_text,
                            ]
                        )

                        # Check if ANY query term matches the searchable text
                        match_found = False
                        for term in query_terms:
                            if term in searchable_text:
                                match_found = True
                                break

                        if match_found:
                            # Extract business_type from tags if present
                            business_type = None
                            for tag in tags:
                                if (
                                    len(tag) >= 2
                                    and tag[0] == "l"
                                    and tag[1]
                                    in [
                                        "retail",  # ProfileType.RETAIL
                                        "restaurant",  # ProfileType.RESTAURANT
                                        "service",  # ProfileType.SERVICE
                                        "business",  # ProfileType.BUSINESS
                                        "entertainment",  # ProfileType.ENTERTAINMENT
                                        "other",  # ProfileType.OTHER
                                    ]
                                ):
                                    business_type = tag[1]
                                    break

                            profile_data["pubkey"] = pubkey
                            profile_data["business_type"] = business_type
                            profile_data["tags"] = tags
                            results.append(profile_data)
                    except json.JSONDecodeError:
                        pass  # Skip invalid JSON

            return results
        except sqlite3.Error as e:
            logger.error(f"Database error when searching profiles: {e}")
            return []

    async def list_profiles(
        self, limit: int = 10, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List profiles with pagination.

        Args:
            limit: Maximum number of profiles to return
            offset: Offset for pagination

        Returns:
            List[Dict[str, Any]]: List of profile data with pubkey, created_at, and tags included

        Raises:
            DatabaseError: If the database connection is not initialized
        """
        if not self._conn:
            raise DatabaseError("Database not initialized")

        try:
            sql = """
            SELECT pubkey, content, created_at, tags FROM events
            WHERE kind = 0
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """

            results = []
            async with self._conn.execute(sql, (limit, offset)) as cursor:
                async for row in cursor:
                    try:
                        pubkey = row[0]
                        profile_data = json.loads(row[1])
                        created_at = row[2]
                        tags = json.loads(row[3])

                        # Extract business_type from tags if present
                        business_type = None
                        for tag in tags:
                            if (
                                len(tag) >= 2
                                and tag[0] == "l"
                                and tag[1]
                                in [
                                    "retail",  # ProfileType.RETAIL
                                    "restaurant",  # ProfileType.RESTAURANT
                                    "service",  # ProfileType.SERVICE
                                    "business",  # ProfileType.BUSINESS
                                    "entertainment",  # ProfileType.ENTERTAINMENT
                                    "other",  # ProfileType.OTHER
                                ]
                            ):
                                business_type = tag[1]
                                break

                        profile_data["pubkey"] = pubkey
                        profile_data["created_at"] = created_at
                        profile_data["business_type"] = business_type
                        profile_data["tags"] = tags
                        results.append(profile_data)
                    except json.JSONDecodeError:
                        pass  # Skip invalid JSON

            return results
        except sqlite3.Error as e:
            logger.error(f"Database error when listing profiles: {e}")
            return []

    async def get_profile_stats(self) -> Dict[str, Any]:
        """Get statistics about profiles in the database.

        Returns:
            Dict[str, Any]: Profile statistics

        Raises:
            DatabaseError: If the database connection is not initialized
        """
        if not self._conn:
            raise DatabaseError("Database not initialized")

        try:
            stats = {}

            # Count total profiles
            async with self._conn.execute(
                "SELECT COUNT(*) FROM events WHERE kind = 0"
            ) as cursor:
                row = await cursor.fetchone()
                stats["total_profiles"] = row[0] if row else 0

            # Count profiles with various fields
            profile_fields = [
                "name",
                "display_name",
                "about",
                "picture",
                "nip05",
                "website",
            ]
            for field in profile_fields:
                async with self._conn.execute(
                    f"SELECT COUNT(*) FROM events WHERE kind = 0 AND json_extract(content, '$.{field}') IS NOT NULL AND json_extract(content, '$.{field}') != ''"
                ) as cursor:
                    row = await cursor.fetchone()
                    stats[f"profiles_with_{field}"] = row[0] if row else 0

            # Get most recent profile update
            async with self._conn.execute(
                "SELECT MAX(created_at) FROM events WHERE kind = 0"
            ) as cursor:
                row = await cursor.fetchone()
                stats["last_updated"] = row[0] if row and row[0] else 0

            return stats
        except sqlite3.Error as e:
            logger.error(f"Database error when getting profile stats: {e}")
            return {"error": str(e)}

    async def search_business_profiles(
        self, query: str = "", business_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for business profiles matching the query and business type.

        Args:
            query: Search query string to match against profile content (optional)
            business_type: Business type filter ("retail", "restaurant", "services", "business", "other")

        Returns:
            List[Dict[str, Any]]: List of matching business profile data with pubkey included

        Raises:
            DatabaseError: If the database connection is not initialized
        """
        if not self._conn:
            raise DatabaseError("Database not initialized")

        try:
            # Convert query to lowercase for case-insensitive search
            query = query.lower()

            sql = """
            SELECT pubkey, content, tags FROM events
            WHERE kind = 0
            ORDER BY created_at DESC
            """

            results = []
            async with self._conn.execute(sql) as cursor:
                async for row in cursor:
                    try:
                        pubkey = row[0]
                        profile_data = json.loads(row[1])
                        tags = json.loads(row[2])

                        # Check if this is a business profile
                        has_business_type_tag = False
                        profile_business_type = None

                        for tag in tags:
                            if len(tag) >= 2:
                                if tag[0] == "L" and tag[1] == "business.type":
                                    has_business_type_tag = True
                                elif tag[0] == "l" and tag[1] in [
                                    "retail",  # ProfileType.RETAIL
                                    "restaurant",  # ProfileType.RESTAURANT
                                    "service",  # ProfileType.SERVICE
                                    "business",  # ProfileType.BUSINESS
                                    "entertainment",  # ProfileType.ENTERTAINMENT
                                    "other",  # ProfileType.OTHER
                                ]:
                                    profile_business_type = tag[1]

                        # Skip if not a business profile
                        if not has_business_type_tag or not profile_business_type:
                            continue

                        # Filter by business type if specified
                        if business_type and profile_business_type != business_type:
                            continue

                        # Check if profile matches search query (if provided)
                        if query:
                            name = str(profile_data.get("name", "")).lower()
                            display_name = str(
                                profile_data.get("display_name", "")
                            ).lower()
                            about = str(profile_data.get("about", "")).lower()
                            nip05 = str(profile_data.get("nip05", "")).lower()
                            # Also search in business_type field
                            business_type_text = str(
                                profile_business_type or ""
                            ).lower()

                            # Search in location and address fields
                            country = str(profile_data.get("country", "")).lower()
                            city = str(profile_data.get("city", "")).lower()
                            state = str(profile_data.get("state", "")).lower()
                            zip_code = str(profile_data.get("zip_code", "")).lower()
                            street = str(profile_data.get("street", "")).lower()

                            # Search in hashtags (convert array to searchable string)
                            hashtags = profile_data.get("hashtags", [])
                            hashtags_text = " ".join(
                                str(tag).lower() for tag in hashtags if tag
                            )

                            if not (
                                query in name
                                or query in display_name
                                or query in about
                                or query in nip05
                                or query in business_type_text
                                or query in country
                                or query in city
                                or query in state
                                or query in zip_code
                                or query in street
                                or query in hashtags_text
                            ):
                                continue

                        # Add business metadata to profile
                        profile_data["pubkey"] = pubkey
                        profile_data["business_type"] = profile_business_type
                        profile_data["tags"] = tags
                        results.append(profile_data)

                    except (json.JSONDecodeError, IndexError):
                        pass  # Skip invalid JSON or malformed tags

            return results
        except sqlite3.Error as e:
            logger.error(f"Database error when searching business profiles: {e}")
            return []

    async def upsert_profile(self, profile_data: Dict[str, Any]) -> bool:
        """Upsert a profile by converting structured profile data to Nostr event format.

        Args:
            profile_data: Dictionary containing profile information with keys like:
                         public_key, name, display_name, about, website, picture, etc.

        Returns:
            bool: True if the profile was successfully stored, False otherwise

        Raises:
            DatabaseError: If the database connection is not initialized
        """
        if not self._conn:
            raise DatabaseError("Database not initialized")

        try:
            # Extract required fields
            public_key = profile_data.get("public_key")
            if not public_key:
                logger.error("Profile data missing required 'public_key' field")
                return False

            # Extract ALL profile fields for the content JSON (matching synvya-sdk Profile model)
            content_fields = {
                "about": profile_data.get("about", ""),
                "banner": profile_data.get("banner", ""),
                "bot": profile_data.get("bot", False),
                "city": profile_data.get("city", ""),
                "country": profile_data.get("country", ""),
                "created_at": profile_data.get("created_at", 0),
                "display_name": profile_data.get("display_name", ""),
                "email": profile_data.get("email", ""),
                "hashtags": profile_data.get("hashtags", []),
                "locations": profile_data.get("locations", []),
                "name": profile_data.get("name", ""),
                "namespace": profile_data.get("namespace", ""),
                "nip05": profile_data.get("nip05", ""),
                "nip05_validated": profile_data.get("nip05_validated", False),
                "picture": profile_data.get("picture", ""),
                "phone": profile_data.get("phone", ""),
                "profile_type": profile_data.get("profile_type", ""),
                "profile_url": profile_data.get("profile_url", ""),
                "state": profile_data.get("state", ""),
                "street": profile_data.get("street", ""),
                "website": profile_data.get("website", ""),
                "zip_code": profile_data.get("zip_code", ""),
                # Legacy fields for backward compatibility
                "lud16": profile_data.get("lud16", ""),
            }

            # Store all fields (including empty ones for complete data)
            content = content_fields

            # Build tags from profile data
            tags = []

            # Add business type tags if present
            if profile_data.get("namespace") == "business.type":
                tags.append(["L", "business.type"])
                if profile_data.get("profile_type"):
                    tags.append(["l", profile_data.get("profile_type")])

            # Add hashtags if present
            hashtags = profile_data.get("hashtags", [])
            if hashtags:
                for hashtag in hashtags:
                    if hashtag:  # Skip empty hashtags
                        tags.append(["t", hashtag])

            # Add location tags if present
            locations = profile_data.get("locations", [])
            if locations:
                for location in locations:
                    if location:  # Skip empty locations
                        tags.append(["g", location])

            # Use last_updated if provided, otherwise use current time
            created_at = profile_data.get("last_updated", int(time.time()))

            # Generate a unique event ID (simplified approach)
            event_id = hashlib.sha256(
                f"{public_key}:0:{created_at}".encode()
            ).hexdigest()

            # Store as a kind 0 (profile) event
            return await self.upsert_event(
                id=event_id,
                pubkey=public_key,
                kind=0,  # Profile event kind
                content=json.dumps(content),
                created_at=created_at,
                tags=tags,
            )

        except Exception as e:
            logger.error(f"Error upserting profile: {e}")
            return False

    async def get_business_types(self) -> List[str]:
        """Get the available business types for filtering business profiles.

        Returns:
            List[str]: List of available business type values
        """
        return [
            "retail",
            "restaurant",
            "service",
            "business",
            "entertainment",
            "other",
        ]

    async def search_stalls(
        self, query: str, pubkey: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for stalls matching the query.

        Args:
            query: Search query string
            pubkey: Optional pubkey to restrict search to a specific merchant

        Returns:
            List[Dict[str, Any]]: List of matching stall data

        Raises:
            DatabaseError: If the database connection is not initialized
        """
        if not self._conn:
            raise DatabaseError("Database not initialized")

        try:
            # Convert query to lowercase for case-insensitive search
            query = query.lower()

            # Build the SQL query based on whether a pubkey is provided
            if pubkey:
                sql = """
                SELECT pubkey, content, d_tag, created_at, tags FROM events
                WHERE kind = 30017 AND pubkey = ?
                ORDER BY created_at DESC
                """
                params = (pubkey,)
            else:
                sql = SQL_GET_ALL_STALLS
                params = ()

            results = []
            async with self._conn.execute(sql, params) as cursor:
                async for row in cursor:
                    try:
                        stall_pubkey = row[0]
                        stall_data = json.loads(row[1])
                        d_tag = row[2]
                        created_at = row[3]
                        tags = json.loads(row[4])

                        # Check if stall matches search query
                        stall_name = str(stall_data.get("name", "")).lower()
                        stall_desc = str(stall_data.get("description", "")).lower()

                        if query in stall_name or query in stall_desc:
                            stall_data["pubkey"] = stall_pubkey
                            stall_data["d_tag"] = d_tag
                            stall_data["created_at"] = created_at
                            stall_data["tags"] = tags
                            results.append(stall_data)
                    except json.JSONDecodeError:
                        pass  # Skip invalid JSON

            return results
        except sqlite3.Error as e:
            logger.error(f"Database error when searching stalls: {e}")
            return []

    async def list_stalls(
        self, limit: int = 10, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """List all stalls with pagination.

        Args:
            limit: Maximum number of stalls to return
            offset: Number of stalls to skip

        Returns:
            List[Dict[str, Any]]: List of stall data with pubkey and metadata included

        Raises:
            DatabaseError: If the database connection is not initialized
        """
        if not self._conn:
            raise DatabaseError("Database not initialized")

        try:
            sql = """
            SELECT pubkey, content, d_tag, created_at, tags FROM events
            WHERE kind = 30017
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """

            results = []
            async with self._conn.execute(sql, (limit, offset)) as cursor:
                async for row in cursor:
                    try:
                        stall_pubkey = row[0]
                        stall_data = json.loads(row[1])
                        d_tag = row[2]
                        created_at = row[3]
                        tags = json.loads(row[4])

                        stall_data["pubkey"] = stall_pubkey
                        stall_data["d_tag"] = d_tag
                        stall_data["created_at"] = created_at
                        stall_data["tags"] = tags
                        results.append(stall_data)
                    except json.JSONDecodeError:
                        pass  # Skip invalid JSON

            return results
        except sqlite3.Error as e:
            logger.error(f"Database error when listing stalls: {e}")
            return []

    async def get_stall_by_pubkey_and_dtag(
        self, pubkey: str, d_tag: str
    ) -> Optional[Dict[str, Any]]:
        """Get a specific stall by pubkey and d-tag.

        Args:
            pubkey: Stall owner's pubkey
            d_tag: Stall identifier (d-tag)

        Returns:
            Optional[Dict[str, Any]]: Stall data or None if not found

        Raises:
            DatabaseError: If the database connection is not initialized
        """
        if not self._conn:
            raise DatabaseError("Database not initialized")

        try:
            async with self._conn.execute(
                """
                SELECT content, created_at, tags FROM events
                WHERE kind = 30017 AND pubkey = ? AND d_tag = ?
                """,
                (pubkey, d_tag),
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None

                stall_data = json.loads(row[0])
                stall_data["pubkey"] = pubkey
                stall_data["d_tag"] = d_tag
                stall_data["created_at"] = row[1]
                stall_data["tags"] = json.loads(row[2])
                return stall_data

        except (sqlite3.Error, json.JSONDecodeError) as e:
            logger.error(f"Database error when getting stall: {e}")
            return None

    async def get_stall_stats(self) -> Dict[str, Any]:
        """Get statistics about stalls in the database.

        Returns:
            Dict[str, Any]: Dictionary containing stall statistics

        Raises:
            DatabaseError: If the database connection is not initialized
        """
        if not self._conn:
            raise DatabaseError("Database not initialized")

        try:
            stats = {}

            # Total stalls
            async with self._conn.execute(
                "SELECT COUNT(*) FROM events WHERE kind = 30017"
            ) as cursor:
                result = await cursor.fetchone()
                stats["total_stalls"] = result[0] if result else 0

            # Stalls by merchant
            async with self._conn.execute(
                """
                SELECT COUNT(DISTINCT pubkey) FROM events WHERE kind = 30017
                """
            ) as cursor:
                result = await cursor.fetchone()
                stats["unique_merchants"] = result[0] if result else 0

            # Most recent stall
            async with self._conn.execute(
                """
                SELECT created_at FROM events WHERE kind = 30017
                ORDER BY created_at DESC LIMIT 1
                """
            ) as cursor:
                result = await cursor.fetchone()
                stats["latest_stall_timestamp"] = result[0] if result else None

            return stats
        except sqlite3.Error as e:
            logger.error(f"Database error when getting stall stats: {e}")
            return {}

    async def clear_all_data(self) -> bool:
        """Clear all data from the database.

        Returns:
            bool: True if successful, False otherwise

        Raises:
            DatabaseError: If the database connection is not initialized
        """
        if not self._conn:
            raise DatabaseError("Database not initialized")

        try:
            await self._conn.execute("DELETE FROM events")
            await self._conn.commit()
            logger.info("Cleared all data from database")
            return True
        except sqlite3.Error as e:
            logger.error(f"Error clearing database: {e}")
            return False
