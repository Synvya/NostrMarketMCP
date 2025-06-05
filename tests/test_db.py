"""Tests for the database module."""

import asyncio
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from nostr_market_mcp.db import Database


@pytest.fixture
def mock_db(mocker):
    """Create a mock database for testing."""
    mock = mocker.MagicMock(spec=Database)

    # Make async methods return awaitable mocks
    mock.initialize = AsyncMock()
    mock.close = AsyncMock()
    mock.upsert_event = AsyncMock(return_value=True)
    mock.get_resource_rows = AsyncMock(return_value=[])
    mock.get_resource_data = AsyncMock(return_value={})
    mock.search_products = AsyncMock(return_value=[])

    return mock


@pytest.mark.asyncio
async def test_upsert_event():
    """Test upserting events with replaceable event logic."""
    # Create a real temporary database for this test
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        # Initialize database
        db = Database(db_path)
        await db.initialize()

        # Prepare test event data
        event_id1 = "event1"
        event_id2 = "event2"
        pubkey = "pubkey123"
        kind = 30018  # Product
        content1 = json.dumps({"name": "Product 1", "price": 10})
        content2 = json.dumps({"name": "Product 1 Updated", "price": 15})
        created_at1 = 1000
        created_at2 = 2000
        d_tag = "product123"
        tags1 = [["d", d_tag]]
        tags2 = [["d", d_tag], ["p", "someother"]]

        # Insert first event
        result = await db.upsert_event(
            event_id1, pubkey, kind, content1, created_at1, tags1
        )
        assert result is True

        # Get the event to verify it was inserted
        rows = await db.get_resource_rows(kind, pubkey, d_tag)
        assert len(rows) == 1
        assert rows[0][0] == event_id1
        assert rows[0][1] == content1

        # Insert second event with newer timestamp for the same (kind, pubkey, d_tag)
        result = await db.upsert_event(
            event_id2, pubkey, kind, content2, created_at2, tags2
        )
        assert result is True

        # Verify newer event replaced the older one
        rows = await db.get_resource_rows(kind, pubkey, d_tag)
        assert len(rows) == 1
        assert rows[0][0] == event_id2
        assert rows[0][1] == content2

        # Try inserting an older event which should not replace newer one
        result = await db.upsert_event(
            "event3", pubkey, kind, "old content", 500, tags1
        )
        assert result is True

        # Verify older event did not replace newer one
        rows = await db.get_resource_rows(kind, pubkey, d_tag)
        assert len(rows) == 1
        assert rows[0][0] == event_id2  # Still the newer one

        # Insert event with no d-tag
        result = await db.upsert_event(
            "event4", pubkey, 0, '{"name":"Merchant Name"}', 3000, []
        )
        assert result is True

        # Verify it was inserted
        rows = await db.get_resource_rows(0, pubkey)
        assert len(rows) == 1
        assert rows[0][0] == "event4"

    finally:
        # Clean up
        await db.close()
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_get_resource_data():
    """Test retrieving resource data for different URI patterns."""
    # Create a real temporary database for this test
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        # Initialize database
        db = Database(db_path)
        await db.initialize()

        # Insert profile event
        pubkey = "pubkey456"
        profile_content = json.dumps(
            {"name": "Test Merchant", "about": "Test merchant description"}
        )
        await db.upsert_event("profile1", pubkey, 0, profile_content, 1000, [])

        # Insert product events
        product1_d = "product1"
        product1_content = json.dumps(
            {
                "id": "prod1",
                "name": "Product 1",
                "price": 10.99,
                "description": "A test product",
            }
        )
        await db.upsert_event(
            "event1", pubkey, 30018, product1_content, 1000, [["d", product1_d]]
        )

        product2_d = "product2"
        product2_content = json.dumps(
            {
                "id": "prod2",
                "name": "Product 2",
                "price": 20.99,
                "description": "Another test product",
            }
        )
        await db.upsert_event(
            "event2", pubkey, 30018, product2_content, 2000, [["d", product2_d]]
        )

        # Test getting profile
        profile_uri = f"nostr://{pubkey}/profile"
        profile_data = await db.get_resource_data(profile_uri)
        assert profile_data is not None
        assert profile_data["name"] == "Test Merchant"

        # Test getting specific product
        product_uri = f"nostr://{pubkey}/product/{product1_d}"
        product_data = await db.get_resource_data(product_uri)
        assert product_data is not None
        assert product_data["name"] == "Product 1"
        assert product_data["price"] == 10.99

        # Test getting catalog
        catalog_uri = f"nostr://{pubkey}/catalog"
        catalog_data = await db.get_resource_data(catalog_uri)
        assert catalog_data is not None
        assert "products" in catalog_data
        assert len(catalog_data["products"]) == 2

        # Test invalid URI
        invalid_uri = f"nostr://{pubkey}/invalid"
        invalid_data = await db.get_resource_data(invalid_uri)
        assert invalid_data is None

        # Test non-existent pubkey
        nonexistent_uri = f"nostr://nonexistent/profile"
        nonexistent_data = await db.get_resource_data(nonexistent_uri)
        assert nonexistent_data is None

    finally:
        # Clean up
        await db.close()
        os.unlink(db_path)


@pytest.mark.asyncio
async def test_search_products():
    """Test searching for products."""
    # Create a real temporary database for this test
    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    try:
        # Initialize database
        db = Database(db_path)
        await db.initialize()

        # Insert product events for different merchants
        pubkey1 = "merchant1"
        pubkey2 = "merchant2"

        # Products for merchant 1
        product1 = json.dumps(
            {
                "id": "prod1",
                "name": "Red T-Shirt",
                "description": "A comfortable cotton t-shirt",
                "price": 19.99,
            }
        )
        await db.upsert_event(
            "event1", pubkey1, 30018, product1, 1000, [["d", "prod1"]]
        )

        product2 = json.dumps(
            {
                "id": "prod2",
                "name": "Blue Jeans",
                "description": "Denim pants",
                "price": 39.99,
            }
        )
        await db.upsert_event(
            "event2", pubkey1, 30018, product2, 1001, [["d", "prod2"]]
        )

        # Products for merchant 2
        product3 = json.dumps(
            {
                "id": "prod3",
                "name": "Green T-Shirt",
                "description": "An organic cotton shirt",
                "price": 24.99,
            }
        )
        await db.upsert_event(
            "event3", pubkey2, 30018, product3, 1002, [["d", "prod3"]]
        )

        # Test search for all merchants
        results = await db.search_products("shirt")
        assert len(results) == 2

        # Test search with merchant filter
        results = await db.search_products("shirt", pubkey1)
        assert len(results) == 1
        assert results[0]["name"] == "Red T-Shirt"

        # Test search in description
        results = await db.search_products("cotton")
        assert len(results) == 2

        # Test search with no results
        results = await db.search_products("nonexistent")
        assert len(results) == 0

    finally:
        # Clean up
        await db.close()
        os.unlink(db_path)
