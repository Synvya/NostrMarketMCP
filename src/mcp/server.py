#!/usr/bin/env python3
"""
Nostr Profiles MCP Server

A Model Context Protocol server that provides access to Nostr profile data.
This server implements MCP over HTTP with JSON-RPC and Server-Sent Events.
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
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from src.core import Database
from src.core.shared_database import close_shared_database, get_shared_database

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

# Refresh interval in seconds (1 hour)
REFRESH_INTERVAL = 3600


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for FastAPI app."""
    # Startup
    logger.info("Starting Nostr Profiles MCP Server")
    await initialize_db()
    yield
    # Shutdown
    logger.info("Shutting down Nostr Profiles MCP Server")
    await cleanup_db()


# Create the FastAPI app for MCP over HTTP
app = FastAPI(title="Nostr Profiles MCP Server", lifespan=lifespan)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global refresh task
refresh_task: Optional[asyncio.Task] = None

# Global NostrClient for searching
nostr_client: Optional[NostrClient] = None

# MCP Server capabilities and info
MCP_SERVER_INFO = {
    "name": "nostr-profiles-mcp",
    "version": "1.0.0",
    "protocolVersion": "2024-11-05",
    "capabilities": {
        "tools": {"listChanged": False},
        "resources": {"subscribe": False, "listChanged": False},
        "logging": {},
        "prompts": {},
    },
}

# Available tools
AVAILABLE_TOOLS = [
    {
        "name": "search_profiles",
        "description": "Search for Nostr profiles by content",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "description": "Maximum results",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_profile_by_pubkey",
        "description": "Get a specific Nostr profile by public key",
        "inputSchema": {
            "type": "object",
            "properties": {
                "pubkey": {"type": "string", "description": "Public key (hex)"}
            },
            "required": ["pubkey"],
        },
    },
    {
        "name": "search_business_profiles",
        "description": "Search for business Nostr profiles",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "business_type": {
                    "type": "string",
                    "description": "Business type filter",
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "description": "Maximum results",
                },
            },
        },
    },
    {
        "name": "get_profile_stats",
        "description": "Get statistics about the profile database",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "refresh_profiles_from_nostr",
        "description": "Manually refresh the database from Nostr relays",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_all_profiles",
        "description": "List all profiles in the database",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "default": 100,
                    "description": "Maximum results",
                }
            },
        },
    },
    {
        "name": "get_business_types",
        "description": "Get all available business types",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "explain_profile_tags",
        "description": "Explain Nostr profile tags",
        "inputSchema": {
            "type": "object",
            "properties": {
                "tags_json": {
                    "type": "string",
                    "description": "JSON string of tags array",
                }
            },
            "required": ["tags_json"],
        },
    },
    {
        "name": "get_refresh_status",
        "description": "Get the status of the database refresh process",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "clear_database",
        "description": "Clear all profiles from the database",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

# Available resources
AVAILABLE_RESOURCES = [
    {
        "uri": "nostr://profiles/{pubkey}",
        "name": "Nostr Profile",
        "description": "A Nostr profile resource",
        "mimeType": "application/json",
    }
]


async def initialize_db():
    """Initialize the shared database connection."""
    # Get the shared database instance - this will create it if it doesn't exist
    await get_shared_database()
    logger.info("MCP server using shared database instance")

    # Skip network operations in test environment
    if getenv("ENVIRONMENT") == "test":
        logger.info("Test environment detected - skipping network operations")
        return

    # Only run initial refresh and start periodic task when first creating the database
    await refresh_database()  # Initial refresh at startup
    await start_refresh_task()  # Start periodic refresh


async def cleanup_db():
    """Cleanup database connection."""
    # Stop refresh task first
    await stop_refresh_task()
    # Close the shared database
    await close_shared_database()


async def ensure_db_initialized():
    """Ensure database is initialized before any operation."""
    # Always use the shared database
    await get_shared_database()


# MCP Tool implementations
async def tool_search_profiles(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Search for Nostr profiles by content."""
    await ensure_db_initialized()
    db = await get_shared_database()

    query = arguments.get("query", "")
    limit = arguments.get("limit", 10)

    try:
        profiles = await db.search_profiles(query)
        limited_profiles = profiles[:limit]
        return {
            "success": True,
            "count": len(limited_profiles),
            "profiles": limited_profiles,
        }
    except Exception as e:
        logger.error(f"Error searching profiles: {e}")
        return {"error": str(e)}


async def tool_get_profile_by_pubkey(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Get a specific Nostr profile by public key."""
    await ensure_db_initialized()
    db = await get_shared_database()

    pubkey = arguments.get("pubkey", "")

    try:
        resource_uri = f"nostr://{pubkey}/profile"
        profile = await db.get_resource_data(resource_uri)
        if profile:
            profile["pubkey"] = pubkey
            return {"success": True, "profile": profile}
        else:
            return {"success": False, "error": "Profile not found"}
    except Exception as e:
        logger.error(f"Error getting profile: {e}")
        return {"error": str(e)}


async def tool_search_business_profiles(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Search for business Nostr profiles."""
    await ensure_db_initialized()
    db = await get_shared_database()

    query = arguments.get("query", "")
    business_type = arguments.get("business_type", "")
    limit = arguments.get("limit", 10)

    try:
        query_param = query if query else ""
        business_type_param = business_type if business_type else None

        profiles = await db.search_business_profiles(query_param, business_type_param)
        limited_profiles = profiles[:limit]

        return {
            "success": True,
            "count": len(limited_profiles),
            "query": query,
            "business_type_filter": business_type or "all",
            "profiles": limited_profiles,
        }
    except Exception as e:
        logger.error(f"Error searching business profiles: {e}")
        return {"error": str(e)}


async def tool_get_profile_stats(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Get statistics about the profile database."""
    await ensure_db_initialized()
    db = await get_shared_database()

    try:
        stats = await db.get_profile_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        return {"error": str(e)}


async def tool_refresh_profiles_from_nostr(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Manually trigger a refresh of the database."""
    await ensure_db_initialized()
    db = await get_shared_database()

    try:
        await refresh_database()
        stats = await db.get_profile_stats()
        return {
            "success": True,
            "message": "Database refresh completed",
            "current_stats": stats,
        }
    except Exception as e:
        logger.error(f"Error in manual refresh: {e}")
        return {"error": str(e)}


async def tool_list_all_profiles(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """List all profiles in the database."""
    await ensure_db_initialized()
    db = await get_shared_database()

    limit = arguments.get("limit", 100)

    try:
        profiles = await db.search_profiles("")  # Empty query returns all
        limited_profiles = profiles[:limit]
        return {
            "success": True,
            "count": len(limited_profiles),
            "total_available": len(profiles),
            "profiles": limited_profiles,
        }
    except Exception as e:
        logger.error(f"Error listing profiles: {e}")
        return {"error": str(e)}


async def tool_get_business_types(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Get all available business types."""
    await ensure_db_initialized()
    db = await get_shared_database()

    try:
        business_types = await db.get_business_types()
        return {
            "success": True,
            "business_types": business_types,
        }
    except Exception as e:
        logger.error(f"Error getting business types: {e}")
        return {"error": str(e)}


async def tool_explain_profile_tags(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Explain Nostr profile tags."""
    tags_json = arguments.get("tags_json", "")

    try:
        tags = json.loads(tags_json)

        explanations = []
        for tag in tags:
            if not isinstance(tag, list) or len(tag) < 2:
                continue

            tag_type = tag[0]
            tag_value = tag[1] if len(tag) > 1 else ""

            if tag_type == "L":
                explanations.append(f"Label namespace: {tag_value}")
            elif tag_type == "l":
                namespace = tag[2] if len(tag) > 2 else ""
                explanations.append(f"Label: {tag_value} (namespace: {namespace})")
            elif tag_type == "t":
                explanations.append(f"Hashtag: #{tag_value}")
            elif tag_type == "p":
                explanations.append(f"Person reference: {tag_value}")
            elif tag_type == "e":
                explanations.append(f"Event reference: {tag_value}")
            else:
                explanations.append(f"Tag type '{tag_type}': {tag_value}")

        return {
            "success": True,
            "explanation": "; ".join(explanations),
            "tag_breakdown": [
                {"type": tag[0], "value": tag[1] if len(tag) > 1 else "", "raw": tag}
                for tag in tags
            ],
        }
    except json.JSONDecodeError as e:
        return {"success": False, "error": f"Invalid JSON: {e}"}
    except Exception as e:
        logger.error(f"Error explaining tags: {e}")
        return {"error": str(e)}


async def tool_get_refresh_status(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Get the status of the database refresh process."""
    global refresh_task, nostr_client

    try:
        return {
            "success": True,
            "database_initialized": True,
            "refresh_task_running": refresh_task is not None
            and not refresh_task.done(),
            "configured_relays": DEFAULT_RELAYS,
            "nostr_client_connected": nostr_client is not None,
        }
    except Exception as e:
        logger.error(f"Error getting refresh status: {e}")
        return {"error": str(e)}


async def tool_clear_database(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Clear all profiles from the database."""
    await ensure_db_initialized()
    db = await get_shared_database()

    try:
        result = await db.clear_all_data()
        if result:
            return {
                "success": True,
                "message": "Database cleared successfully",
            }
        else:
            return {
                "success": False,
                "error": "Failed to clear database",
            }
    except Exception as e:
        logger.error(f"Error clearing database: {e}")
        return {"error": str(e)}


# Tool registry
TOOL_REGISTRY = {
    "search_profiles": tool_search_profiles,
    "get_profile_by_pubkey": tool_get_profile_by_pubkey,
    "search_business_profiles": tool_search_business_profiles,
    "get_profile_stats": tool_get_profile_stats,
    "refresh_profiles_from_nostr": tool_refresh_profiles_from_nostr,
    "list_all_profiles": tool_list_all_profiles,
    "get_business_types": tool_get_business_types,
    "explain_profile_tags": tool_explain_profile_tags,
    "get_refresh_status": tool_get_refresh_status,
    "clear_database": tool_clear_database,
}


async def handle_mcp_request(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP JSON-RPC request."""
    method = request_data.get("method")
    params = request_data.get("params", {})
    request_id = request_data.get("id")

    try:
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": MCP_SERVER_INFO["protocolVersion"],
                    "capabilities": MCP_SERVER_INFO["capabilities"],
                    "serverInfo": {
                        "name": MCP_SERVER_INFO["name"],
                        "version": MCP_SERVER_INFO["version"],
                    },
                },
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": AVAILABLE_TOOLS},
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if tool_name not in TOOL_REGISTRY:
                raise ValueError(f"Unknown tool: {tool_name}")

            result = await TOOL_REGISTRY[tool_name](arguments)

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
                },
            }

        elif method == "resources/list":
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"resources": AVAILABLE_RESOURCES},
            }

        elif method == "resources/read":
            uri = params.get("uri", "")
            # Handle resource reading (simplified for now)
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "application/json",
                            "text": json.dumps(
                                {"message": "Resource reading not fully implemented"}
                            ),
                        }
                    ]
                },
            }

        else:
            raise ValueError(f"Unknown method: {method}")

    except Exception as e:
        logger.error(f"Error handling MCP request: {e}")
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": -32603, "message": "Internal error", "data": str(e)},
        }


@app.post("/mcp")
async def mcp_endpoint(request: Request):
    """Main MCP endpoint for JSON-RPC requests with optional SSE streaming."""
    try:
        request_data = await request.json()

        # Check if client wants streaming response via Accept header
        accept_header = request.headers.get("accept", "")
        wants_streaming = "text/event-stream" in accept_header

        if wants_streaming:
            # Return Server-Sent Events stream
            async def generate_sse():
                response = await handle_mcp_request(request_data)
                # Send the response as SSE
                yield f"data: {json.dumps(response)}\n\n"

            return StreamingResponse(
                generate_sse(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "*",
                },
            )
        else:
            # Return JSON directly for non-streaming clients
            response = await handle_mcp_request(request_data)
            return response

    except Exception as e:
        logger.error(f"Error in MCP endpoint: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/mcp/sse")
async def mcp_sse_endpoint():
    """Server-Sent Events endpoint for MCP streaming."""

    async def generate_sse():
        # Send initial connection message
        yield f"data: {json.dumps({'type': 'connection', 'status': 'connected'})}\n\n"

        # Keep connection alive
        try:
            while True:
                # Send periodic heartbeat
                yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': time.time()})}\n\n"
                await asyncio.sleep(30)  # Heartbeat every 30 seconds
        except asyncio.CancelledError:
            yield f"data: {json.dumps({'type': 'connection', 'status': 'disconnected'})}\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "nostr-profiles-mcp-server",
        "version": MCP_SERVER_INFO["version"],
        "protocol": "MCP over HTTP with SSE",
        "endpoints": {
            "mcp": "/mcp (POST - JSON-RPC)",
            "sse": "/mcp/sse (GET - Server-Sent Events)",
            "health": "/health (GET)",
        },
    }


# Include the refresh database and other utility functions from the original server
async def refresh_database():
    """Refresh the database with new Nostr profile data."""
    global nostr_client

    # Get the shared database instance
    db = await get_shared_database()
    all_profiles: set[Profile] = set()

    try:
        logger.info("Refreshing database with new Nostr profile data...")

        # Connect to Nostr relays if not already connected
        if nostr_client is None:
            logger.debug(f"Connecting to relays: {DEFAULT_RELAYS}")
            try:
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
                    for profile in profiles:
                        logger.debug(f"Profile: {profile.to_json()}")

            logger.info(
                f"Total unique profiles found across all business types: {len(all_profiles)}"
            )

        except Exception as e:
            logger.error("Failed to get merchants: %s", e)
            raise

        # Store the profiles in the database
        logger.debug(f"Found {len(all_profiles)} business profiles to store")
        profile_count = 0

        # Update database with profile information
        for profile in all_profiles:
            try:
                # Use the Profile's built-in to_dict() method which handles set serialization
                profile_data = profile.to_dict()

                # Add additional fields needed by the database
                profile_data["public_key"] = profile.get_public_key("hex")
                profile_data["business_type"] = (
                    profile.profile_type.value if profile.profile_type else None
                )
                profile_data["tags"] = getattr(profile, "tags", [])
                profile_data["created_at"] = profile.get_created_at()
                profile_data["last_updated"] = profile.get_created_at()

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
                    result = await db.upsert_profile(profile_data)
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


# Startup and shutdown are now handled by the lifespan context manager


if __name__ == "__main__":
    import uvicorn

    host = getenv("HOST", "0.0.0.0")
    port = int(getenv("PORT", "8081"))

    logger.info(f"Starting MCP server on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)
