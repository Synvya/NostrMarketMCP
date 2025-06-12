"""Nostr ingestion worker for NostrMarketMCP.

Subscribes to Nostr events and writes them to the database.
"""

import asyncio
import logging
import sys
from typing import Callable, List, Optional, Set

# Try to import from the real SDK, fall back to mocks for testing
try:
    from synvya_sdk.nostr import NostrClient
except ImportError:
    if "pytest" in sys.modules:
        from tests.mocks.synvya_sdk.nostr import NostrClient
    else:
        raise

from nostr_market_mcp.db import Database

logger = logging.getLogger(__name__)

# Nostr event kinds to subscribe to
PROFILE_KIND = 0  # NIP-01 metadata
PRODUCT_KIND = 30018  # NIP-15 product


class NostrIngestWorker:
    """Worker that subscribes to Nostr events and writes them to the database."""

    def __init__(
        self,
        db: Database,
        pubkey: Optional[str] = None,
        relays: Optional[List[str]] = None,
        on_event_cb: Optional[Callable] = None,
    ) -> None:
        """Initialize the worker.

        Args:
            db: Database instance
            pubkey: Optional specific pubkey to monitor (if None, monitors all)
            relays: List of relay URLs to connect to
            on_event_cb: Optional callback to invoke when an event is processed
        """
        self.db = db
        self.pubkey = pubkey
        self.relays = relays or [
            "wss://relay.damus.io",
            "wss://nos.lol",
            "wss://relay.snort.social",
        ]
        self.client: Optional[NostrClient] = None
        self.on_event_cb = on_event_cb
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Start the ingestion worker.

        Connects to the relays and subscribes to events.
        """
        if self.pubkey:
            logger.info(
                f"Starting Nostr profile ingestion worker for pubkey {self.pubkey}"
            )
        else:
            logger.info("Starting Nostr profile ingestion worker for all profiles")
        logger.info(f"Connecting to relays: {', '.join(self.relays)}")

        try:
            # Connect to relays
            self.client = await NostrClient.create(self.relays, private_key=None)

            # Subscribe to profile metadata
            if self.pubkey:
                subscription_id = await self.client.subscribe(
                    kinds=[PROFILE_KIND],
                    authors=[self.pubkey],
                    id="synvya-profile-events",
                )
            else:
                subscription_id = await self.client.subscribe(
                    kinds=[PROFILE_KIND],
                    authors=None,
                    id="synvya-profile-events",
                )

            logger.info(
                f"Subscribed to profile events with subscription ID: {subscription_id}"
            )

            # Process events until stopped
            async for event in self.client.get_events():
                if self._stop_event.is_set():
                    break

                await self._process_event(event)

        except Exception as e:
            logger.error(f"Error in Nostr ingestion worker: {e}")
            raise
        finally:
            if self.client:
                await self.client.close()
                self.client = None
            logger.info("Nostr ingestion worker stopped")

    async def stop(self) -> None:
        """Stop the ingestion worker."""
        logger.info("Stopping Nostr ingestion worker")
        self._stop_event.set()
        if self.client:
            await self.client.close()
            self.client = None

    async def _process_event(self, event: dict) -> None:
        """Process a Nostr event and store it in the database.

        Args:
            event: Nostr event dictionary
        """
        try:
            # Extract event fields
            event_id = event.get("id", "")
            pubkey = event.get("pubkey", "")
            kind = event.get("kind", 0)
            content = event.get("content", "")
            created_at = event.get("created_at", 0)
            tags = event.get("tags", [])

            # Validate required fields
            if not all([event_id, pubkey, content]):
                logger.warning(f"Skipping invalid event: {event_id}")
                return

            # If monitoring specific pubkey, only process events from that pubkey
            if self.pubkey and pubkey != self.pubkey:
                return

            # Only process profile metadata events
            if kind != PROFILE_KIND:
                return

            # Store the event in the database
            success = await self.db.upsert_event(
                event_id, pubkey, kind, content, created_at, tags
            )

            if success:
                logger.info(
                    f"Processed profile event: pubkey={pubkey[:8]}..., id={event_id[:8]}..."
                )

                # Invoke callback if provided
                if self.on_event_cb:
                    await self.on_event_cb(event)
            else:
                logger.warning(
                    f"Failed to store profile event: pubkey={pubkey[:8]}..., id={event_id[:8]}..."
                )

        except Exception as e:
            logger.error(f"Error processing event: {e}")


class NostrIngestManager:
    """Manager for running multiple Nostr ingestion workers."""

    def __init__(self, db: Database) -> None:
        """Initialize the manager.

        Args:
            db: Database instance
        """
        self.db = db
        self.workers: Set[NostrIngestWorker] = set()
        self._tasks: Set[asyncio.Task] = set()

    async def add_worker(
        self,
        pubkey: Optional[str] = None,
        relays: Optional[List[str]] = None,
        on_event_cb: Optional[Callable] = None,
    ) -> NostrIngestWorker:
        """Add a new ingestion worker and start it.

        Args:
            pubkey: Optional specific pubkey to monitor (if None, monitors all)
            relays: List of relay URLs to connect to
            on_event_cb: Optional callback to invoke when an event is processed

        Returns:
            NostrIngestWorker: The created worker instance
        """
        worker = NostrIngestWorker(self.db, pubkey, relays, on_event_cb)
        self.workers.add(worker)

        # Start the worker in a background task
        task = asyncio.create_task(worker.start())

        # Add done callback to remove task when finished
        task.add_done_callback(self._task_done)
        self._tasks.add(task)

        return worker

    async def stop_all(self) -> None:
        """Stop all ingestion workers."""
        logger.info("Stopping all Nostr ingestion workers")

        # Stop all workers
        await asyncio.gather(*(worker.stop() for worker in self.workers))

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        self.workers.clear()
        self._tasks.clear()

    def _task_done(self, task: asyncio.Task) -> None:
        """Callback invoked when a worker task is done.

        Args:
            task: The completed task
        """
        # Remove the task from the set
        self._tasks.discard(task)

        # Check for exceptions
        if not task.cancelled():
            exc = task.exception()
            if exc:
                logger.error(f"Worker task failed with exception: {exc}")
