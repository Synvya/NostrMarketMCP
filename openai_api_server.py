#!/usr/bin/env python3
"""
OpenAI Compatible REST API Server for Nostr Profiles

Provides REST API endpoints that can be used with OpenAI Custom GPTs and Actions.
Wraps the existing MCP server functionality.
"""

import asyncio
import json
import logging
import ssl
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Import our existing MCP server functionality
sys.path.insert(0, str(Path(__file__).parent))
from nostr_market_mcp.db import Database

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DEFAULT_DB_PATH = Path.home() / ".nostr_profiles.db"

# Global database instance
db: Optional[Database] = None

# Create FastAPI app
app = FastAPI(
    title="Nostr Profiles API",
    description="API for searching and managing Nostr profile data, specifically business profiles with L/business.type tags",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware for web integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for request/response validation
class SearchProfilesRequest(BaseModel):
    query: str = Field(
        ..., description="The search term to look for in profile content"
    )
    limit: int = Field(
        10, description="Maximum number of results to return", ge=1, le=100
    )


class BusinessProfilesRequest(BaseModel):
    query: str = Field("", description="Optional search term for profile content")
    business_type: str = Field(
        "",
        description="Business type filter: retail, restaurant, services, business, entertainment, other, or empty for all",
    )
    limit: int = Field(
        10, description="Maximum number of results to return", ge=1, le=100
    )


class Profile(BaseModel):
    pubkey: str
    name: Optional[str] = None
    display_name: Optional[str] = None
    about: Optional[str] = None
    picture: Optional[str] = None
    banner: Optional[str] = None
    website: Optional[str] = None
    nip05: Optional[str] = None
    bot: Optional[bool] = None
    business_type: Optional[str] = None


class SearchResponse(BaseModel):
    success: bool
    count: int
    profiles: List[Profile]
    query: Optional[str] = None


class StatsResponse(BaseModel):
    success: bool
    stats: Dict[str, Any]


class RefreshResponse(BaseModel):
    success: bool
    message: str
    current_stats: Dict[str, Any]


class BusinessTypesResponse(BaseModel):
    success: bool
    business_types: List[str]
    description: str


# Database dependency
async def get_database():
    """Get database instance, initialize if needed."""
    global db
    if db is None:
        db = Database(DEFAULT_DB_PATH)
        await db.initialize()
        logger.info(f"Database initialized at {DEFAULT_DB_PATH}")
    return db


# API Endpoints


@app.get("/", summary="API Information")
async def root():
    """Get basic API information."""
    return {
        "name": "Nostr Profiles API",
        "description": "API for searching and managing Nostr profile data",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "search_profiles": "/api/search_profiles",
            "search_business_profiles": "/api/search_business_profiles",
            "get_profile": "/api/profile/{pubkey}",
            "get_stats": "/api/stats",
            "refresh": "/api/refresh",
            "business_types": "/api/business_types",
        },
    }


@app.post(
    "/api/search_profiles", response_model=SearchResponse, summary="Search Profiles"
)
async def search_profiles(
    request: SearchProfilesRequest, database: Database = Depends(get_database)
):
    """
    Search for Nostr profiles by content.

    Searches profile metadata including name, about, nip05, and other fields.
    """
    try:
        profiles = await database.search_profiles(request.query)
        limited_profiles = profiles[: request.limit]

        # Convert to Profile models
        profile_objects = []
        for profile_data in limited_profiles:
            profile_objects.append(Profile(**profile_data))

        return SearchResponse(
            success=True,
            count=len(profile_objects),
            profiles=profile_objects,
            query=request.query,
        )
    except Exception as e:
        logger.error(f"Error searching profiles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(
    "/api/search_business_profiles",
    response_model=SearchResponse,
    summary="Search Business Profiles",
)
async def search_business_profiles(
    request: BusinessProfilesRequest, database: Database = Depends(get_database)
):
    """
    Search for business Nostr profiles with specific business type tags.

    Filters profiles that have:
    - Tag "L" with value "business.type"
    - Tag "l" with value matching business_type parameter
    """
    try:
        # Convert empty string to None for database method
        query_param = request.query if request.query else ""
        business_type_param = request.business_type if request.business_type else None

        profiles = await database.search_business_profiles(
            query_param, business_type_param
        )
        limited_profiles = profiles[: request.limit]

        # Convert to Profile models
        profile_objects = []
        for profile_data in limited_profiles:
            profile_objects.append(Profile(**profile_data))

        return SearchResponse(
            success=True,
            count=len(profile_objects),
            profiles=profile_objects,
            query=request.query,
        )
    except Exception as e:
        logger.error(f"Error searching business profiles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/profile/{pubkey}",
    response_model=Dict[str, Any],
    summary="Get Profile by Public Key",
)
async def get_profile_by_pubkey(
    pubkey: str, database: Database = Depends(get_database)
):
    """Get a specific Nostr profile by its public key."""
    try:
        # Use get_resource_data with profile URI
        resource_uri = f"nostr://{pubkey}/profile"
        profile = await database.get_resource_data(resource_uri)

        if profile:
            # Add pubkey to the profile data
            profile["pubkey"] = pubkey
            return {"success": True, "profile": Profile(**profile)}
        else:
            raise HTTPException(status_code=404, detail="Profile not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats", response_model=StatsResponse, summary="Get Database Statistics")
async def get_profile_stats(database: Database = Depends(get_database)):
    """Get statistics about the profile database."""
    try:
        stats = await database.get_profile_stats()
        return StatsResponse(success=True, stats=stats)
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/api/business_types",
    response_model=BusinessTypesResponse,
    summary="Get Business Types",
)
async def get_business_types():
    """Get the available business types for filtering business profiles."""
    business_types = [
        "retail",
        "restaurant",
        "services",
        "business",
        "entertainment",
        "other",
    ]

    return BusinessTypesResponse(
        success=True,
        business_types=business_types,
        description="Available values for business_type parameter in search_business_profiles",
    )


@app.post("/api/refresh", response_model=RefreshResponse, summary="Refresh Database")
async def refresh_profiles_from_nostr(database: Database = Depends(get_database)):
    """
    Manually trigger a refresh of the database by searching for new business profiles from Nostr relays.

    This will search for kind:0 profiles that have the tag "L" "business.type" from the configured relays.
    """
    try:
        # Import refresh functionality
        from nostr_profiles_mcp_server import refresh_database

        await refresh_database()

        stats = await database.get_profile_stats()
        return RefreshResponse(
            success=True, message="Database refresh completed", current_stats=stats
        )
    except Exception as e:
        logger.error(f"Error in manual refresh: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Health check endpoint
@app.get("/health", summary="Health Check")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "nostr-profiles-api"}


# OpenAPI schema customization for better OpenAI integration
@app.get("/openapi.json", include_in_schema=False)
async def custom_openapi():
    """Custom OpenAPI schema optimized for OpenAI Actions."""
    from fastapi.openapi.utils import get_openapi

    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Nostr Profiles API",
        version="1.0.0",
        description="API for searching and managing Nostr profile data, specifically business profiles",
        routes=app.routes,
    )

    # Customize for OpenAI Actions
    openapi_schema["info"]["x-logo"] = {"url": "https://nostr.com/favicon.ico"}

    app.openapi_schema = openapi_schema
    return app.openapi_schema


if __name__ == "__main__":
    # Check if we can run HTTPS for OpenAI Custom GPT compatibility
    import os

    # For development, you can create self-signed certificates with:
    # openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
    ssl_keyfile = "/Users/alejandro/Synvya/NostrMarketMCP/key.pem"
    ssl_certfile = "/Users/alejandro/Synvya/NostrMarketMCP/cert.pem"

    if os.path.exists(ssl_keyfile) and os.path.exists(ssl_certfile):
        # Run with HTTPS on port 443 (requires sudo/admin privileges)
        print("Running with HTTPS on port 443 (default HTTPS port)")
        print("Note: Port 443 requires administrator privileges")
        print("Run with: sudo python openai_api_server.py")
        try:
            uvicorn.run(
                "openai_api_server:app",
                host="localhost",
                port=443,
                reload=False,  # Disable reload when running as sudo
                log_level="info",
                ssl_keyfile=ssl_keyfile,
                ssl_certfile=ssl_certfile,
            )
        except PermissionError:
            print(
                "ERROR: Permission denied. Port 443 requires administrator privileges."
            )
            print("Please run: sudo python openai_api_server.py")
            print("Or use the fallback HTTP server on port 8081")
            # Fallback to port 8081
            uvicorn.run(
                "openai_api_server:app",
                host="localhost",
                port=8081,
                reload=True,
                log_level="info",
                ssl_keyfile=ssl_keyfile,
                ssl_certfile=ssl_certfile,
            )
    else:
        # Fallback to HTTP for local development
        print("Running with HTTP (create key.pem and cert.pem for HTTPS)")
        print("For OpenAI Custom GPTs, you need HTTPS on port 443")
        uvicorn.run(
            "openai_api_server:app",
            host="localhost",
            port=8081,
            reload=True,
            log_level="info",
        )
