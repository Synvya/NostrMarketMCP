"""Command-line interface for NostrMarketMCP."""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

import click
import uvicorn

from nostr_market_mcp import __version__
from nostr_market_mcp.db import Database
from nostr_market_mcp.ingest import NostrIngestManager
from nostr_market_mcp.server import create_mcp_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()],
)

logger = logging.getLogger("nostr_market_mcp")

# Default database path in user's home directory
DEFAULT_DB_PATH = str(Path.home() / ".nostr_profiles.db")


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """NostrMarketMCP CLI tool for managing Nostr profile data."""
    logging.basicConfig(level=logging.INFO)


@main.command()
@click.option(
    "--db-path",
    type=click.Path(),
    default=DEFAULT_DB_PATH,
    help="Path to SQLite database file",
)
def migrate(db_path: str) -> None:
    """Initialize/migrate the database schema."""

    async def _migrate() -> None:
        db = Database(Path(db_path))
        await db.initialize()
        await db.close()
        logger.info(f"Database schema initialized at {db_path}")

    asyncio.run(_migrate())


@main.command()
@click.option(
    "--db-path",
    type=click.Path(),
    default=DEFAULT_DB_PATH,
    help="Path to SQLite database file",
)
@click.option(
    "--pubkey",
    help="Specific Nostr pubkey to monitor (optional - if not specified, monitors all profiles)",
)
@click.option(
    "--relays",
    help="Comma-separated list of Nostr relay URLs (optional - uses defaults if not specified)",
)
def ingest(db_path: str, pubkey: Optional[str], relays: Optional[str]) -> None:
    """Run the Nostr profile ingestion worker."""
    db_path = Path(db_path)
    relay_list = [r.strip() for r in relays.split(",")] if relays else None

    if pubkey:
        logger.info(f"Starting profile ingestion worker for pubkey: {pubkey}")
    else:
        logger.info("Starting profile ingestion worker for all profiles")

    if relay_list:
        logger.info(f"Using relays: {relay_list}")
    else:
        logger.info("Using default relays")

    async def _run_ingest() -> None:
        # Initialize database
        db = Database(db_path)
        await db.initialize()

        try:
            # Create and start the ingestion manager
            manager = NostrIngestManager(db)

            # Add a worker for the specified pubkey (or all if none specified)
            await manager.add_worker(pubkey, relay_list)

            # Keep running until interrupted
            while True:
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("Ingestion worker stopping due to keyboard interrupt")
        except Exception as e:
            logger.error(f"Error in ingestion worker: {e}")
            raise
        finally:
            # Stop all workers and close database
            await manager.stop_all()
            await db.close()

    asyncio.run(_run_ingest())


@main.command()
@click.option(
    "--db-path",
    type=click.Path(),
    default=DEFAULT_DB_PATH,
    help="Path to SQLite database file",
)
@click.option(
    "--host",
    default="0.0.0.0",
    help="Host to bind the MCP server to",
)
@click.option(
    "--port",
    type=int,
    default=8000,
    help="Port to run the MCP server on",
)
def serve(
    db_path: str,
    host: str,
    port: int,
) -> None:
    """Run the MCP profile server."""
    db_path = Path(db_path)

    # Check if we need to create the database
    if not db_path.exists():
        logger.warning(f"Database file {db_path} does not exist, creating it")

        async def _init_db():
            db = Database(db_path)
            await db.initialize()
            await db.close()

        asyncio.run(_init_db())

    # Initialize database and create FastAPI app
    async def _setup_app():
        db = Database(db_path)
        await db.initialize()
        app, _ = create_mcp_app(db)
        return app

    # Create the FastAPI app
    app = asyncio.run(_setup_app())

    # Start the server
    logger.info(f"Starting MCP profile server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


@main.command()
@click.option(
    "--db-path",
    type=click.Path(),
    default=DEFAULT_DB_PATH,
    help="Path to SQLite database file",
)
@click.option(
    "--pubkey",
    help="Specific Nostr pubkey to monitor (optional)",
)
@click.option(
    "--relays",
    help="Comma-separated list of Nostr relay URLs (optional)",
)
@click.option(
    "--host",
    default="0.0.0.0",
    help="Host to bind the MCP server to",
)
@click.option(
    "--port",
    type=int,
    default=8000,
    help="Port to run the MCP server on",
)
def run(
    db_path: str,
    pubkey: Optional[str],
    relays: Optional[str],
    host: str,
    port: int,
) -> None:
    """Run both profile ingestion worker and MCP server together."""
    db_path = Path(db_path)
    relay_list = [r.strip() for r in relays.split(",")] if relays else None

    async def _run_all() -> None:
        # Initialize database
        db = Database(db_path)
        await db.initialize()

        try:
            # Create and start the ingestion manager
            ingest_manager = NostrIngestManager(db)

            # Add a worker for the specified pubkey (or all if none specified)
            worker = await ingest_manager.add_worker(pubkey, relay_list)

            # Create FastAPI app with MCP server
            app, mcp_server = create_mcp_app(db)

            # Set up ingestion callback to notify MCP clients
            async def on_event(event: dict) -> None:
                # Extract event details
                pubkey = event.get("pubkey", "")
                kind = event.get("kind", 0)

                # Only process profile events
                if kind == 0:  # Profile
                    uri = f"nostr://{pubkey}/profile"

                    # Get resource data
                    data = await db.get_resource_data(uri)
                    if data:
                        # Notify MCP clients
                        await mcp_server.notify_resource_update(uri, data)

            # Set the callback for the worker
            # Note: This requires modifying the worker after creation
            worker.on_event_cb = on_event

            # Start Uvicorn server
            config = uvicorn.Config(app, host=host, port=port, log_level="info")
            server = uvicorn.Server(config)
            logger.info(f"Starting MCP profile server on {host}:{port}")

            await server.serve()

        except KeyboardInterrupt:
            logger.info("Shutting down due to keyboard interrupt")
        except Exception as e:
            logger.error(f"Error running services: {e}")
            raise
        finally:
            # Stop all workers and close database
            await ingest_manager.stop_all()
            await db.close()

    asyncio.run(_run_all())


@main.command()
@click.option(
    "--db-path",
    type=click.Path(),
    default=DEFAULT_DB_PATH,
    help="Path to SQLite database file",
)
def add_sample_data(db_path: str) -> None:
    """Add sample profile data for testing."""
    db_path = Path(db_path)

    # Sample profile from user's example
    sample_profile = {
        "content": {
            "name": "test",
            "display_name": "Test Unit",
            "about": "Testing for the sake of testing...",
            "picture": "https://blossom.band/650ccd2a489b3717566a67bbabbbf32f28f2b458d39a3f155d998a00f2aab8a8",
            "banner": "https://blossom.band/f2a00732b50318b2230917863377eef95edc32a7d93d4165054a466ca46535f9",
            "website": "https://www.synvya.com",
            "nip05": "test@synvya.com",
            "bot": False,
        },
        "created_at": 1749063276,
        "id": "53324d4b6c90a696c372902f2e7a99838768223e234df438bd0d8e0fffda59b0",
        "kind": 0,
        "pubkey": "57d03534460df449321cde3757b1b379a8377bace8199101df0716e20dbb7991",
        "sig": "93ca9eddd18a0f4b42d7b74f3f3108639022c90a9e30e0bfb89a4811f4240021cb539b110ee9e93a44d19f61bee954759cbbc380e4d5284ee577f87e96bae692",
        "tags": [
            ["L", "business.email"],
            ["l", "test@synvya.com", "business.email"],
            ["L", "business.phone"],
            ["l", "+15551234567", "business.phone"],
            ["L", "business.location"],
            ["l", "123 Unit St., Testfield, DE, 90001, USA", "business.location"],
            ["L", "business.type"],
            ["l", "retail", "business.type"],
            ["t", "software"],
            ["t", "memes"],
        ],
        "originalContent": '{"name":"test","display_name":"Test Unit","about":"Testing for the sake of testing...","picture":"https://blossom.band/650ccd2a489b3717566a67bbabbbf32f28f2b458d39a3f155d998a00f2aab8a8","banner":"https://blossom.band/f2a00732b50318b2230917863377eef95edc32a7d93d4165054a466ca46535f9","website":"https://www.synvya.com","nip05":"test@synvya.com","bot":false}',
    }

    async def _add_sample() -> None:
        db = Database(db_path)
        await db.initialize()

        try:
            # Insert the sample profile
            content_json = json.dumps(sample_profile["content"])
            success = await db.upsert_event(
                sample_profile["id"],
                sample_profile["pubkey"],
                sample_profile["kind"],
                content_json,
                sample_profile["created_at"],
                sample_profile["tags"],
            )

            if success:
                logger.info(
                    f"Successfully added sample profile for pubkey: {sample_profile['pubkey']}"
                )
            else:
                logger.error("Failed to add sample profile")

        except Exception as e:
            logger.error(f"Error adding sample profile: {e}")
        finally:
            await db.close()

    asyncio.run(_add_sample())


if __name__ == "__main__":
    main()
