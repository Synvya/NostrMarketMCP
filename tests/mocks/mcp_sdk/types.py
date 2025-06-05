"""Mock MCP SDK data types for testing."""

from typing import Any, Dict, List, Optional


class Resource:
    """Resource descriptor."""

    def __init__(self, uri: str, name: str) -> None:
        """Initialize a resource.

        Args:
            uri: Resource URI
            name: Resource name
        """
        self.uri = uri
        self.name = name


class ResourceList:
    """List of resources."""

    def __init__(self, resources: List[Resource]) -> None:
        """Initialize a resource list.

        Args:
            resources: List of resources
        """
        self.resources = resources


class ResourceData:
    """Resource data container."""

    def __init__(self, data: Dict[str, Any]) -> None:
        """Initialize resource data.

        Args:
            data: Resource data
        """
        self.data = data


class ToolSpec:
    """Tool specification."""

    def __init__(
        self, name: str, description: str, param_schema: Dict[str, Any]
    ) -> None:
        """Initialize a tool specification.

        Args:
            name: Tool name
            description: Tool description
            param_schema: Tool parameter schema
        """
        self.name = name
        self.description = description
        self.param_schema = param_schema


class ToolSpecs:
    """List of tool specifications."""

    def __init__(self, tools: List[ToolSpec]) -> None:
        """Initialize a list of tool specifications.

        Args:
            tools: List of tool specifications
        """
        self.tools = tools


class ToolCall:
    """Tool call request."""

    def __init__(self, name: str, params: Dict[str, Any]) -> None:
        """Initialize a tool call.

        Args:
            name: Tool name
            params: Tool parameters
        """
        self.name = name
        self.params = params
