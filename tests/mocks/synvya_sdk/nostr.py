"""Mock NostrClient for testing."""

from typing import Any, AsyncGenerator, Dict, List, Optional


class NostrClient:
    """Mock NostrClient for testing."""

    @classmethod
    async def create(
        cls, relays: List[str], private_key: Optional[str] = None
    ) -> "NostrClient":
        """Create a new NostrClient instance.

        Args:
            relays: List of relay URLs to connect to
            private_key: Optional private key for signing (not used in mock)

        Returns:
            NostrClient: New client instance
        """
        return cls()

    async def subscribe(
        self, kinds: List[int], authors: Optional[List[str]], id: str
    ) -> str:
        """Subscribe to events.

        Args:
            kinds: Event kinds to subscribe to
            authors: Event authors to subscribe to (None for all authors)
            id: Subscription ID

        Returns:
            str: Subscription ID
        """
        return id

    async def get_events(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Get events from the subscription.

        Returns:
            AsyncGenerator of events (for testing, returns empty generator)
        """
        # Return empty async generator for testing
        return
        yield  # This line will never execute but makes this an async generator

    async def close(self) -> None:
        """Close the client connection."""
        pass
