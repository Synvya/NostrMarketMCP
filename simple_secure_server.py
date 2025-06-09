#!/usr/bin/env python3
"""
Simple Secure API Server for Nostr Profiles - OpenAI Custom GPT Compatible

Production-ready API server with essential security measures using minimal dependencies.
Designed specifically for OpenAI Custom GPT integration with proper CORS and authentication.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

# Import our simplified security module and database
sys.path.insert(0, str(Path(__file__).parent))
from nostr_market_mcp.db import Database
from security_simple import (
    SECURITY_CONFIG,
    SECURITY_HEADERS,
    InputValidator,
    SecureBusinessSearchRequest,
    SecureSearchRequest,
    auth,
    rate_limiter,
    security_middleware,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DEFAULT_DB_PATH = os.getenv("DATABASE_PATH", str(Path.home() / ".nostr_profiles.db"))

# Global database instance
db: Optional[Database] = None

# Create FastAPI app with security settings
app = FastAPI(
    title="Secure Nostr Profiles API",
    description="Production-ready API for searching Nostr profile data - OpenAI Custom GPT Compatible",
    version="1.0.0",
    docs_url="/docs" if SECURITY_CONFIG["ENVIRONMENT"] != "production" else None,
    redoc_url="/redoc" if SECURITY_CONFIG["ENVIRONMENT"] != "production" else None,
    openapi_url=(
        "/openapi.json" if SECURITY_CONFIG["ENVIRONMENT"] != "production" else None
    ),
)

# Configure CORS for OpenAI Custom GPT compatibility
allowed_origins = (
    SECURITY_CONFIG["ALLOWED_ORIGINS"]
    if SECURITY_CONFIG["ALLOWED_ORIGINS"]
    else ["https://platform.openai.com"]
)

# Always ensure OpenAI platform is included
if "https://platform.openai.com" not in allowed_origins:
    allowed_origins.append("https://platform.openai.com")

logger.info(f"CORS allowed origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    expose_headers=["X-Total-Count", "X-Rate-Limit-Remaining"],
)


# Security middleware with rate limiting
@app.middleware("http")
async def security_middleware_handler(request: Request, call_next):
    """Apply security middleware to all requests."""
    try:
        # Get client IP for rate limiting
        client_ip = security_middleware.get_client_ip(request)

        # Check rate limits
        if not rate_limiter.is_allowed(
            client_ip,
            SECURITY_CONFIG["RATE_LIMIT_REQUESTS"],
            SECURITY_CONFIG["RATE_LIMIT_WINDOW"],
        ):
            logger.warning(f"Rate limit exceeded for {client_ip}")
            return Response(
                status_code=429,
                content=json.dumps({"error": "Rate limit exceeded"}),
                media_type="application/json",
            )

        # Security checks
        await security_middleware.process_request(request)

        # Process request
        response = await call_next(request)

        # Add security headers
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value

        return response
    except Exception as e:
        logger.error(f"Security middleware error: {e}")
        raise HTTPException(status_code=500, detail="Security check failed")


# Authentication dependency
async def get_authenticated_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(
        HTTPBearer(auto_error=False)
    ),
):
    """Verify authentication credentials."""
    api_key_valid = False
    bearer_token_valid = False

    # Try API key authentication
    try:
        await auth.verify_api_key(request)
        api_key_valid = True
    except Exception as e:
        logger.debug(f"API key authentication failed: {e}")

    # Try Bearer token authentication
    try:
        await auth.verify_bearer_token(credentials)
        bearer_token_valid = True
    except Exception as e:
        logger.debug(f"Bearer token authentication failed: {e}")

    # If either authentication method succeeded, allow access
    if api_key_valid or bearer_token_valid:
        return True

    # If both methods are configured but both failed, raise error
    if SECURITY_CONFIG["API_KEY"] and SECURITY_CONFIG["BEARER_TOKEN"]:
        raise HTTPException(
            status_code=401, detail="Valid API key or Bearer token required"
        )
    elif SECURITY_CONFIG["API_KEY"]:
        raise HTTPException(status_code=401, detail="Valid API key required")
    elif SECURITY_CONFIG["BEARER_TOKEN"]:
        raise HTTPException(status_code=401, detail="Valid Bearer token required")
    else:
        # No authentication configured
        return True


# Database dependency
async def get_database() -> Database:
    """Get database instance, creating if necessary."""
    global db
    if db is None:
        db = Database(DEFAULT_DB_PATH)
        await db.initialize()
        logger.info(f"Database initialized: {DEFAULT_DB_PATH}")

        # Share the database instance with the MCP server
        from nostr_profiles_mcp_server import set_shared_database

        set_shared_database(db)

    return db


# Response models
class Profile(BaseModel):
    """Profile model with validation."""

    pubkey: str = Field(..., description="Public key of the profile")
    name: Optional[str] = Field(None, description="Display name")
    about: Optional[str] = Field(None, description="Profile description")
    picture: Optional[str] = Field(None, description="Profile picture URL")
    nip05: Optional[str] = Field(None, description="NIP-05 verification")
    website: Optional[str] = Field(None, description="Website URL")
    business_type: Optional[str] = Field(
        None, description="Business type if applicable"
    )


class SearchResponse(BaseModel):
    """Search response model."""

    success: bool = Field(True, description="Whether the request was successful")
    count: int = Field(..., description="Number of profiles returned")
    profiles: List[Profile] = Field(..., description="List of matching profiles")
    query: Optional[str] = Field(None, description="Search query used")


class StatsResponse(BaseModel):
    """Statistics response model."""

    success: bool = Field(True, description="Whether the request was successful")
    stats: Dict[str, Any] = Field(..., description="Database statistics")


class RefreshResponse(BaseModel):
    """Refresh response model."""

    success: bool = Field(True, description="Whether the refresh was successful")
    message: str = Field(..., description="Refresh status message")
    current_stats: Optional[Dict[str, Any]] = Field(
        None, description="Updated statistics"
    )


# API endpoints
@app.get("/health", summary="Health Check")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "secure-nostr-profiles-api",
        "version": "1.0.0",
        "environment": SECURITY_CONFIG["ENVIRONMENT"],
        "auth_configured": bool(
            SECURITY_CONFIG["API_KEY"] or SECURITY_CONFIG["BEARER_TOKEN"]
        ),
    }


@app.post(
    "/api/search_profiles",
    response_model=SearchResponse,
    summary="Search Profiles",
    dependencies=(
        [Depends(get_authenticated_user)]
        if SECURITY_CONFIG["API_KEY"] or SECURITY_CONFIG["BEARER_TOKEN"]
        else []
    ),
)
async def search_profiles(
    request: SecureSearchRequest, database: Database = Depends(get_database)
):
    """Search for Nostr profiles by content with secure validation."""
    try:
        logger.info(f"Profile search: query='{request.query}', limit={request.limit}")

        profiles = await database.search_profiles(request.query)
        limited_profiles = profiles[: request.limit]

        # Convert to Profile models with validation
        profile_objects = []
        for profile_data in limited_profiles:
            try:
                # Sanitize profile data
                sanitized_data = {}
                for key, value in profile_data.items():
                    if isinstance(value, str):
                        sanitized_data[key] = InputValidator.sanitize_string(
                            value, max_length=1000
                        )
                    else:
                        sanitized_data[key] = value

                profile_objects.append(Profile(**sanitized_data))
            except Exception as e:
                logger.warning(
                    f"Invalid profile data for {profile_data.get('pubkey', 'unknown')}: {e}"
                )
                continue

        logger.info(f"Profile search completed: {len(profile_objects)} results")
        return SearchResponse(
            success=True,
            count=len(profile_objects),
            profiles=profile_objects,
            query=request.query,
        )
    except Exception as e:
        logger.error(f"Profile search error: {e}")
        raise HTTPException(status_code=500, detail="Search failed")


@app.post(
    "/api/search_business_profiles",
    response_model=SearchResponse,
    summary="Search Business Profiles",
    dependencies=(
        [Depends(get_authenticated_user)]
        if SECURITY_CONFIG["API_KEY"] or SECURITY_CONFIG["BEARER_TOKEN"]
        else []
    ),
)
async def search_business_profiles(
    request: SecureBusinessSearchRequest, database: Database = Depends(get_database)
):
    """Search for business Nostr profiles with secure validation."""
    try:
        logger.info(
            f"Business profile search: query='{request.query}', business_type='{request.business_type}', limit={request.limit}"
        )

        profiles = await database.search_business_profiles(
            request.query if request.query else "",
            request.business_type if request.business_type else None,
        )
        limited_profiles = profiles[: request.limit]

        # Convert to Profile models with validation
        profile_objects = []
        for profile_data in limited_profiles:
            try:
                sanitized_data = {}
                for key, value in profile_data.items():
                    if isinstance(value, str):
                        sanitized_data[key] = InputValidator.sanitize_string(
                            value, max_length=1000
                        )
                    else:
                        sanitized_data[key] = value

                profile_objects.append(Profile(**sanitized_data))
            except Exception as e:
                logger.warning(
                    f"Invalid business profile data for {profile_data.get('pubkey', 'unknown')}: {e}"
                )
                continue

        logger.info(
            f"Business profile search completed: {len(profile_objects)} results"
        )
        return SearchResponse(
            success=True,
            count=len(profile_objects),
            profiles=profile_objects,
            query=request.query,
        )
    except Exception as e:
        logger.error(f"Business profile search error: {e}")
        raise HTTPException(status_code=500, detail="Business search failed")


@app.get(
    "/api/profile/{pubkey}",
    response_model=Dict[str, Any],
    summary="Get Profile by Public Key",
    dependencies=(
        [Depends(get_authenticated_user)]
        if SECURITY_CONFIG["API_KEY"] or SECURITY_CONFIG["BEARER_TOKEN"]
        else []
    ),
)
async def get_profile_by_pubkey(
    pubkey: str, database: Database = Depends(get_database)
):
    """Get a specific Nostr profile by its public key with validation."""
    try:
        # Validate pubkey format
        validated_pubkey = InputValidator.validate_pubkey(pubkey)
        logger.info(f"Profile lookup: {validated_pubkey[:8]}...")

        resource_uri = f"nostr://{validated_pubkey}/profile"
        profile = await database.get_resource_data(resource_uri)

        if profile:
            # Sanitize profile data
            sanitized_data = {}
            for key, value in profile.items():
                if isinstance(value, str):
                    sanitized_data[key] = InputValidator.sanitize_string(
                        value, max_length=1000
                    )
                else:
                    sanitized_data[key] = value

            sanitized_data["pubkey"] = validated_pubkey

            logger.info(f"Profile found: {validated_pubkey[:8]}...")
            return {"success": True, "profile": Profile(**sanitized_data)}
        else:
            logger.info(f"Profile not found: {validated_pubkey[:8]}...")
            raise HTTPException(status_code=404, detail="Profile not found")
    except ValueError as e:
        logger.warning(f"Invalid pubkey format '{pubkey}': {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Profile lookup error: {e}")
        raise HTTPException(status_code=500, detail="Profile lookup failed")


@app.get(
    "/api/stats",
    response_model=StatsResponse,
    summary="Get Database Statistics",
    dependencies=(
        [Depends(get_authenticated_user)]
        if SECURITY_CONFIG["API_KEY"] or SECURITY_CONFIG["BEARER_TOKEN"]
        else []
    ),
)
async def get_profile_stats(database: Database = Depends(get_database)):
    """Get statistics about the profile database."""
    try:
        logger.info("Stats request")
        stats = await database.get_profile_stats()
        logger.info(f"Stats retrieved: {stats.get('total_profiles', 0)} total profiles")
        return StatsResponse(success=True, stats=stats)
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail="Stats retrieval failed")


@app.get(
    "/api/business_types",
    summary="Get Available Business Types",
    dependencies=(
        [Depends(get_authenticated_user)]
        if SECURITY_CONFIG["API_KEY"] or SECURITY_CONFIG["BEARER_TOKEN"]
        else []
    ),
)
async def get_business_types(database: Database = Depends(get_database)):
    """Get the list of available business types."""
    try:
        business_types = await database.get_business_types()
        return {
            "success": True,
            "business_types": business_types,
            "count": len(business_types),
        }
    except Exception as e:
        logger.error(f"Business types error: {e}")
        raise HTTPException(status_code=500, detail="Business types retrieval failed")


@app.post(
    "/api/refresh",
    response_model=RefreshResponse,
    summary="Refresh Database",
    dependencies=(
        [Depends(get_authenticated_user)]
        if SECURITY_CONFIG["API_KEY"] or SECURITY_CONFIG["BEARER_TOKEN"]
        else []
    ),
)
async def refresh_profiles_from_nostr(database: Database = Depends(get_database)):
    """Manually trigger a refresh of the database."""
    try:
        logger.info("Manual refresh triggered")

        # Import refresh functionality
        from nostr_profiles_mcp_server import refresh_database

        await refresh_database()

        stats = await database.get_profile_stats()
        logger.info(f"Manual refresh completed: {stats}")

        return RefreshResponse(
            success=True, message="Database refresh completed", current_stats=stats
        )
    except Exception as e:
        logger.error(f"Manual refresh error: {e}")
        raise HTTPException(status_code=500, detail="Refresh failed")


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    return Response(
        status_code=500,
        content=json.dumps(
            {
                "success": False,
                "error": "Internal server error",
                "detail": "An unexpected error occurred",
            }
        ),
        media_type="application/json",
    )


# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    """Initialize database and logging on startup."""
    logger.info("Starting Secure Nostr Profiles API")
    logger.info(f"Environment: {SECURITY_CONFIG['ENVIRONMENT']}")
    logger.info(
        f"Authentication enabled: {bool(SECURITY_CONFIG['API_KEY'] or SECURITY_CONFIG['BEARER_TOKEN'])}"
    )
    logger.info(f"CORS origins: {allowed_origins}")

    # Initialize database
    await get_database()


@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown."""
    logger.info("Shutting down Secure Nostr Profiles API")
    if db:
        await db.close()


if __name__ == "__main__":
    # Server configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    log_level = os.getenv("LOG_LEVEL", "info").lower()

    logger.info(f"Starting server on {host}:{port}")

    # Run with uvicorn
    uvicorn.run(
        "simple_secure_server:app",
        host=host,
        port=port,
        log_level=log_level,
        access_log=True,
        reload=False,
    )
