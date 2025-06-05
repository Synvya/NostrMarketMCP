"""Mock MCPServer class for testing."""

from typing import Any, Callable, Dict, List, Optional

from fastapi import Depends, FastAPI, Request, Response


class ResourceEvent:
    """Resource event for notifications."""

    def __init__(self, uri: str, data: Dict[str, Any]) -> None:
        """Initialize a resource event.

        Args:
            uri: Resource URI
            data: Resource data
        """
        self.uri = uri
        self.data = data


class MCPServer:
    """Mock MCPServer for testing."""

    def __init__(self, app: FastAPI) -> None:
        """Initialize the server.

        Args:
            app: FastAPI app to attach to
        """
        self.app = app
        self.resources_list_handler = None
        self.resources_read_handler = None
        self.tools_list_handler = None
        self.tools_call_handler = None
        self.client_connect_handler = None
        self.client_disconnect_handler = None

    def register_resources_list_handler(
        self, handler: Callable, dependencies: Optional[List] = None
    ) -> None:
        """Register handler for listing resources.

        Args:
            handler: Handler function
            dependencies: List of dependencies
        """
        self.resources_list_handler = handler

    def register_resources_read_handler(
        self, handler: Callable, dependencies: Optional[List] = None
    ) -> None:
        """Register handler for reading resources.

        Args:
            handler: Handler function
            dependencies: List of dependencies
        """
        self.resources_read_handler = handler

    def register_tools_list_handler(
        self, handler: Callable, dependencies: Optional[List] = None
    ) -> None:
        """Register handler for listing tools.

        Args:
            handler: Handler function
            dependencies: List of dependencies
        """
        self.tools_list_handler = handler

    def register_tools_call_handler(
        self, handler: Callable, dependencies: Optional[List] = None
    ) -> None:
        """Register handler for calling tools.

        Args:
            handler: Handler function
            dependencies: List of dependencies
        """
        self.tools_call_handler = handler

    def register_client_connect_handler(self, handler: Callable) -> None:
        """Register handler for client connections.

        Args:
            handler: Handler function
        """
        self.client_connect_handler = handler

    def register_client_disconnect_handler(self, handler: Callable) -> None:
        """Register handler for client disconnections.

        Args:
            handler: Handler function
        """
        self.client_disconnect_handler = handler

    async def notify_resources_updated(self, events: List[ResourceEvent]) -> None:
        """Notify clients about resource updates.

        Args:
            events: List of resource events
        """
        pass
