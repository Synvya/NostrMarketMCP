"""MCP server implementation for NostrMarketMCP.

Exposes profile resources and tools through a simple HTTP interface.
Maps handlers to DB queries for Nostr profiles.
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Set, Tuple, Union, cast

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from nostr_market_mcp.db import Database

logger = logging.getLogger(__name__)


# Authentication middleware
class AuthMiddleware:
    """Bearer token authentication middleware."""

    def __init__(self) -> None:
        self.security = HTTPBearer()
        self.bearer_token = os.environ.get("MCP_BEARER")

        if not self.bearer_token:
            logger.warning(
                "MCP_BEARER environment variable not set; authentication disabled"
            )

    async def verify_token(
        self, credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())
    ) -> bool:
        """Verify bearer token from the request.

        Args:
            credentials: Bearer credentials from the request

        Returns:
            bool: True if valid token or no token required

        Raises:
            HTTPException: If token is invalid
        """
        if not self.bearer_token:
            return True  # No token required

        if credentials.credentials != self.bearer_token:
            raise HTTPException(
                status_code=401, detail="Invalid authentication credentials"
            )
        return True


# Models for tool schemas
class ProfileSearchParams(BaseModel):
    """Parameters for profile search tool."""

    query: str = Field(..., description="Search query for finding profiles")
    pubkey: Optional[str] = Field(
        None, description="Optional specific pubkey to look up"
    )


class ProfileListParams(BaseModel):
    """Parameters for listing profiles."""

    limit: Optional[int] = Field(10, description="Maximum number of profiles to return")
    offset: Optional[int] = Field(0, description="Offset for pagination")


class StallSearchParams(BaseModel):
    """Parameters for stall search tool."""

    query: str = Field(..., description="Search query for finding stalls")
    pubkey: Optional[str] = Field(
        None, description="Optional pubkey to limit search to specific merchant"
    )


class StallListParams(BaseModel):
    """Parameters for listing stalls."""

    limit: Optional[int] = Field(10, description="Maximum number of stalls to return")
    offset: Optional[int] = Field(0, description="Offset for pagination")


class StallByIdParams(BaseModel):
    """Parameters for getting a stall by pubkey and d-tag."""

    pubkey: str = Field(..., description="Merchant's public key")
    d_tag: str = Field(..., description="Stall identifier (d-tag)")


class ProductSearchParams(BaseModel):
    """Parameters for product search tool."""

    query: str = Field(..., description="Search query for finding products")
    pubkey: Optional[str] = Field(
        None, description="Optional pubkey to limit search to specific merchant"
    )


class ProductListParams(BaseModel):
    """Parameters for listing products."""

    limit: Optional[int] = Field(10, description="Maximum number of products to return")
    offset: Optional[int] = Field(0, description="Offset for pagination")


class ProductByIdParams(BaseModel):
    """Parameters for getting a product by pubkey and d-tag."""

    pubkey: str = Field(..., description="Merchant's public key")
    d_tag: str = Field(..., description="Product identifier (d-tag)")


# Simple MCP-like interface for profiles
class ProfileMCPServer:
    """Profile MCP server that provides resources and tools for Nostr profiles."""

    def __init__(self, db: Database, app: FastAPI) -> None:
        """Initialize the profile MCP server.

        Args:
            db: Database instance for resource access
            app: FastAPI app to attach endpoints to
        """
        self.db = db
        self.app = app
        self.auth = AuthMiddleware()

        # Register endpoints
        self._register_endpoints()

    def _register_endpoints(self) -> None:
        """Register all profile endpoints."""

        @self.app.get("/mcp/profiles/{pubkey}")
        async def get_profile(pubkey: str):
            """Get a specific Nostr profile by pubkey."""
            try:
                profile_data = await self.db.get_resource_data(
                    f"nostr://{pubkey}/profile"
                )
                if not profile_data:
                    return {
                        "error": f"Profile not found for pubkey: {pubkey}",
                        "pubkey": pubkey,
                    }

                # Add metadata
                profile_data["pubkey"] = pubkey
                profile_data["resource_type"] = "profile"
                return profile_data
            except Exception as e:
                logger.error(f"Error retrieving profile for {pubkey}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/mcp/tools/search_profiles")
        async def search_profiles(params: ProfileSearchParams):
            """Search for Nostr profiles by content."""
            try:
                if params.pubkey:
                    # Direct lookup by pubkey
                    profile_data = await self.db.get_resource_data(
                        f"nostr://{params.pubkey}/profile"
                    )
                    if profile_data:
                        profile_data["pubkey"] = params.pubkey
                        return {"profiles": [profile_data]}
                    else:
                        return {
                            "profiles": [],
                            "message": f"No profile found for pubkey: {params.pubkey}",
                        }
                else:
                    # Search profiles by content
                    results = await self.db.search_profiles(params.query)
                    return {
                        "profiles": results,
                        "query": params.query,
                        "count": len(results),
                    }
            except Exception as e:
                logger.error(f"Error searching profiles: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/mcp/tools/get_profile_by_pubkey")
        async def get_profile_by_pubkey(params: Dict[str, str]):
            """Get a specific profile by its pubkey."""
            pubkey = params.get("pubkey")
            if not pubkey:
                raise HTTPException(
                    status_code=400, detail="pubkey parameter is required"
                )

            try:
                profile_data = await self.db.get_resource_data(
                    f"nostr://{pubkey}/profile"
                )
                if not profile_data:
                    return {"error": f"Profile not found for pubkey: {pubkey}"}

                profile_data["pubkey"] = pubkey
                return profile_data
            except Exception as e:
                logger.error(f"Error retrieving profile: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/mcp/tools/list_all_profiles")
        async def list_all_profiles(params: ProfileListParams):
            """List all available profiles in the database."""
            try:
                # Clamp limit to reasonable bounds
                limit = max(1, min(params.limit or 10, 100))
                offset = max(0, params.offset or 0)

                profiles = await self.db.list_profiles(limit, offset)
                return {
                    "profiles": profiles,
                    "limit": limit,
                    "offset": offset,
                    "count": len(profiles),
                }
            except Exception as e:
                logger.error(f"Error listing profiles: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/mcp/tools/get_profile_stats")
        async def get_profile_stats():
            """Get statistics about the profiles in the database."""
            try:
                stats = await self.db.get_profile_stats()
                return stats
            except Exception as e:
                logger.error(f"Error getting profile stats: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/mcp/stalls/{pubkey}")
        async def get_stalls(pubkey: str):
            """Get all stalls for a specific merchant by pubkey."""
            try:
                stalls_data = await self.db.get_resource_data(
                    f"nostr://{pubkey}/stalls"
                )
                if not stalls_data:
                    return {
                        "stalls": [],
                        "message": f"No stalls found for pubkey: {pubkey}",
                        "pubkey": pubkey,
                    }

                # Add metadata
                stalls_data["pubkey"] = pubkey
                stalls_data["resource_type"] = "stalls"
                return stalls_data
            except Exception as e:
                logger.error(f"Error retrieving stalls for {pubkey}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/mcp/stall/{pubkey}/{d_tag}")
        async def get_stall(pubkey: str, d_tag: str):
            """Get a specific stall by pubkey and d-tag."""
            try:
                stall_data = await self.db.get_resource_data(
                    f"nostr://{pubkey}/stall/{d_tag}"
                )
                if not stall_data:
                    return {
                        "error": f"Stall not found for pubkey: {pubkey}, d_tag: {d_tag}",
                        "pubkey": pubkey,
                        "d_tag": d_tag,
                    }

                # Add metadata
                stall_data["pubkey"] = pubkey
                stall_data["d_tag"] = d_tag
                stall_data["resource_type"] = "stall"
                return stall_data
            except Exception as e:
                logger.error(f"Error retrieving stall for {pubkey}/{d_tag}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/mcp/tools/search_stalls")
        async def search_stalls(params: StallSearchParams):
            """Search for marketplace stalls by content."""
            try:
                results = await self.db.search_stalls(params.query, params.pubkey)
                return {
                    "stalls": results,
                    "query": params.query,
                    "pubkey_filter": params.pubkey,
                    "count": len(results),
                }
            except Exception as e:
                logger.error(f"Error searching stalls: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/mcp/tools/list_all_stalls")
        async def list_all_stalls(params: StallListParams):
            """List all available stalls in the database."""
            try:
                # Clamp limit to reasonable bounds
                limit = max(1, min(params.limit or 10, 100))
                offset = max(0, params.offset or 0)

                stalls = await self.db.list_stalls(limit, offset)
                return {
                    "stalls": stalls,
                    "limit": limit,
                    "offset": offset,
                    "count": len(stalls),
                }
            except Exception as e:
                logger.error(f"Error listing stalls: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/mcp/tools/get_stall_by_pubkey_and_dtag")
        async def get_stall_by_pubkey_and_dtag(params: StallByIdParams):
            """Get a specific stall by its pubkey and d-tag."""
            try:
                stall_data = await self.db.get_stall_by_pubkey_and_dtag(
                    params.pubkey, params.d_tag
                )
                if not stall_data:
                    return {
                        "error": f"Stall not found for pubkey: {params.pubkey}, d_tag: {params.d_tag}"
                    }

                return stall_data
            except Exception as e:
                logger.error(f"Error retrieving stall: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/mcp/tools/get_stall_stats")
        async def get_stall_stats():
            """Get statistics about the stalls in the database."""
            try:
                stats = await self.db.get_stall_stats()
                return stats
            except Exception as e:
                logger.error(f"Error getting stall stats: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/mcp/products/{pubkey}")
        async def get_products(pubkey: str):
            """Get all products for a specific merchant by pubkey."""
            try:
                products_data = await self.db.get_resource_data(
                    f"nostr://{pubkey}/catalog"
                )
                if not products_data:
                    return {
                        "products": [],
                        "message": f"No products found for pubkey: {pubkey}",
                        "pubkey": pubkey,
                    }

                # Add metadata
                products_data["pubkey"] = pubkey
                products_data["resource_type"] = "products"
                return products_data
            except Exception as e:
                logger.error(f"Error retrieving products for {pubkey}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/mcp/product/{pubkey}/{d_tag}")
        async def get_product(pubkey: str, d_tag: str):
            """Get a specific product by pubkey and d-tag."""
            try:
                product_data = await self.db.get_resource_data(
                    f"nostr://{pubkey}/product/{d_tag}"
                )
                if not product_data:
                    return {
                        "error": f"Product not found for pubkey: {pubkey}, d_tag: {d_tag}",
                        "pubkey": pubkey,
                        "d_tag": d_tag,
                    }

                # Add metadata
                product_data["pubkey"] = pubkey
                product_data["d_tag"] = d_tag
                product_data["resource_type"] = "product"
                return product_data
            except Exception as e:
                logger.error(f"Error retrieving product for {pubkey}/{d_tag}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/mcp/tools/search_products")
        async def search_products(params: ProductSearchParams):
            """Search for marketplace products by content."""
            try:
                results = await self.db.search_products(params.query, params.pubkey)
                return {
                    "products": results,
                    "query": params.query,
                    "pubkey_filter": params.pubkey,
                    "count": len(results),
                }
            except Exception as e:
                logger.error(f"Error searching products: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/mcp/tools/list_all_products")
        async def list_all_products(params: ProductListParams):
            """List all available products in the database."""
            try:
                # Clamp limit to reasonable bounds
                limit = max(1, min(params.limit or 10, 100))
                offset = max(0, params.offset or 0)

                products = await self.db.list_products(limit, offset)
                return {
                    "products": products,
                    "limit": limit,
                    "offset": offset,
                    "count": len(products),
                }
            except Exception as e:
                logger.error(f"Error listing products: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.post("/mcp/tools/get_product_by_pubkey_and_dtag")
        async def get_product_by_pubkey_and_dtag(params: ProductByIdParams):
            """Get a specific product by its pubkey and d-tag."""
            try:
                product_data = await self.db.get_product_by_pubkey_and_dtag(
                    params.pubkey, params.d_tag
                )
                if not product_data:
                    return {
                        "error": f"Product not found for pubkey: {params.pubkey}, d_tag: {params.d_tag}"
                    }

                return product_data
            except Exception as e:
                logger.error(f"Error retrieving product: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/mcp/tools/get_product_stats")
        async def get_product_stats():
            """Get statistics about the products in the database."""
            try:
                stats = await self.db.get_product_stats()
                return stats
            except Exception as e:
                logger.error(f"Error getting product stats: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/mcp/info")
        async def get_server_info():
            """Get information about this MCP server."""
            return {
                "name": "NostrMarketMCP",
                "version": "0.1.0",
                "description": "MCP server for Nostr profile and marketplace data",
                "capabilities": {
                    "resources": ["profiles", "stalls", "products"],
                    "tools": [
                        "search_profiles",
                        "get_profile_by_pubkey",
                        "list_all_profiles",
                        "get_profile_stats",
                        "search_stalls",
                        "list_all_stalls",
                        "get_stall_by_pubkey_and_dtag",
                        "get_stall_stats",
                        "search_products",
                        "list_all_products",
                        "get_product_by_pubkey_and_dtag",
                        "get_product_stats",
                    ],
                },
            }

    async def notify_resource_update(self, uri: str, data: Dict[str, Any]) -> None:
        """Notify connected clients about a resource update.

        Args:
            uri: Resource URI that was updated
            data: Updated resource data
        """
        try:
            logger.info(f"Profile resource updated: {uri}")
        except Exception as e:
            logger.error(f"Error sending resource update notification: {e}")


def create_mcp_app(db: Database) -> Tuple[FastAPI, ProfileMCPServer]:
    """Create a FastAPI app with MCP profile server attached.

    Args:
        db: Database instance for resource access

    Returns:
        Tuple[FastAPI, ProfileMCPServer]: FastAPI app and ProfileMCPServer instance
    """
    # Create FastAPI app
    app = FastAPI(title="NostrProfileMCP", version="0.1.0")

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Create and return profile MCP server
    profile_server = ProfileMCPServer(db, app)

    return app, profile_server
