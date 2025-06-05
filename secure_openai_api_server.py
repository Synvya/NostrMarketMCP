#!/usr/bin/env python3
"""
Secure OpenAI Compatible REST API Server for Nostr Profiles

Production-ready API server with comprehensive security measures including:
- API key and Bearer token authentication
- Rate limiting per IP
- Input validation and sanitization
- Security headers
- Request logging and monitoring
- CORS configuration
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, ValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# Load environment variables
load_dotenv()

# Import our security module and database
sys.path.insert(0, str(Path(__file__).parent))
from nostr_market_mcp.db import Database
from security import (
    SECURITY_CONFIG,
    SECURITY_HEADERS,
    InputValidator,
    SecureBusinessSearchRequest,
    SecureSearchRequest,
    auth,
    custom_rate_limit_exceeded_handler,
    limiter,
    rate_limit,
    security_middleware,
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Database configuration
DEFAULT_DB_PATH = os.getenv("DATABASE_PATH", str(Path.home() / ".nostr_profiles.db"))

# Global database instance
db: Optional[Database] = None

# Create FastAPI app with security settings
app = FastAPI(
    title="Secure Nostr Profiles API",
    description="Production-ready API for searching and managing Nostr profile data with comprehensive security",
    version="1.0.0",
    docs_url="/docs" if SECURITY_CONFIG["ENVIRONMENT"] != "production" else None,
    redoc_url="/redoc" if SECURITY_CONFIG["ENVIRONMENT"] != "production" else None,
    openapi_url=(
        "/openapi.json" if SECURITY_CONFIG["ENVIRONMENT"] != "production" else None
    ),
)

# Add rate limiting middleware
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, custom_rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# Add CORS middleware with secure configuration
allowed_origins = (
    SECURITY_CONFIG["ALLOWED_ORIGINS"] if SECURITY_CONFIG["ALLOWED_ORIGINS"] else ["*"]
)
if SECURITY_CONFIG["ENVIRONMENT"] == "production" and "*" in allowed_origins:
    logger.warning("CORS allows all origins in production - configure ALLOWED_ORIGINS")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
    expose_headers=["X-Total-Count", "X-Rate-Limit-Remaining"],
)


# Security middleware
@app.middleware("http")
async def security_middleware_handler(request: Request, call_next):
    """Apply security middleware to all requests."""
    try:
        # Security checks
        await security_middleware.process_request(request)

        # Process request
        response = await call_next(request)

        # Add security headers
        for header, value in SECURITY_HEADERS.items():
            response.headers[header] = value

        return response
    except Exception as e:
        logger.error("Security middleware error", error=str(e), path=request.url.path)
        raise HTTPException(status_code=500, detail="Security check failed")


# Authentication dependency
async def get_authenticated_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(
        HTTPBearer(auto_error=False)
    ),
):
    """Verify authentication credentials."""
    try:
        # Check API key authentication
        await auth.verify_api_key(request)

        # Check Bearer token authentication
        await auth.verify_bearer_token(credentials)

        return True
    except Exception as e:
        logger.warning("Authentication failed", error=str(e), path=request.url.path)
        raise


# Database dependency
async def get_database() -> Database:
    """Get database instance, creating if necessary."""
    global db
    if db is None:
        db = Database(DEFAULT_DB_PATH)
        await db.initialize()
        logger.info("Database initialized", path=DEFAULT_DB_PATH)
    return db


# Pydantic models for responses
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


class ErrorResponse(BaseModel):
    """Error response model."""

    success: bool = Field(False, description="Always false for errors")
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")


# API endpoints with security
@app.get("/health", summary="Health Check")
@rate_limit(requests_per_window=10)  # More restrictive for health endpoint
async def health_check(request: Request):
    """Health check endpoint with basic system info."""
    return {
        "status": "healthy",
        "service": "secure-nostr-profiles-api",
        "version": "1.0.0",
        "environment": SECURITY_CONFIG["ENVIRONMENT"],
    }


@app.post(
    "/api/search_profiles",
    response_model=SearchResponse,
    summary="Search Profiles",
    dependencies=[Depends(get_authenticated_user)],
)
@rate_limit()
async def search_profiles(
    request: SecureSearchRequest,
    req: Request,
    database: Database = Depends(get_database),
):
    """Search for Nostr profiles by content with secure validation."""
    try:
        logger.info("Profile search", query=request.query, limit=request.limit)

        profiles = await database.search_profiles(request.query)
        limited_profiles = profiles[: request.limit]

        # Convert to Profile models with validation
        profile_objects = []
        for profile_data in limited_profiles:
            try:
                # Validate and sanitize profile data
                sanitized_data = {}
                for key, value in profile_data.items():
                    if isinstance(value, str):
                        sanitized_data[key] = InputValidator.sanitize_string(
                            value, max_length=1000
                        )
                    else:
                        sanitized_data[key] = value

                profile_objects.append(Profile(**sanitized_data))
            except ValidationError as e:
                logger.warning(
                    "Invalid profile data",
                    profile_id=profile_data.get("pubkey", "unknown"),
                    error=str(e),
                )
                continue

        logger.info("Profile search completed", count=len(profile_objects))
        return SearchResponse(
            success=True,
            count=len(profile_objects),
            profiles=profile_objects,
            query=request.query,
        )
    except Exception as e:
        logger.error("Profile search error", error=str(e))
        raise HTTPException(status_code=500, detail="Search failed")


@app.post(
    "/api/search_business_profiles",
    response_model=SearchResponse,
    summary="Search Business Profiles",
    dependencies=[Depends(get_authenticated_user)],
)
@rate_limit()
async def search_business_profiles(
    request: SecureBusinessSearchRequest,
    req: Request,
    database: Database = Depends(get_database),
):
    """Search for business Nostr profiles with secure validation."""
    try:
        logger.info(
            "Business profile search",
            query=request.query,
            business_type=request.business_type,
            limit=request.limit,
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
            except ValidationError as e:
                logger.warning(
                    "Invalid business profile data",
                    profile_id=profile_data.get("pubkey", "unknown"),
                    error=str(e),
                )
                continue

        logger.info("Business profile search completed", count=len(profile_objects))
        return SearchResponse(
            success=True,
            count=len(profile_objects),
            profiles=profile_objects,
            query=request.query,
        )
    except Exception as e:
        logger.error("Business profile search error", error=str(e))
        raise HTTPException(status_code=500, detail="Business search failed")


@app.get(
    "/api/profile/{pubkey}",
    response_model=Dict[str, Any],
    summary="Get Profile by Public Key",
    dependencies=[Depends(get_authenticated_user)],
)
@rate_limit()
async def get_profile_by_pubkey(
    pubkey: str, req: Request, database: Database = Depends(get_database)
):
    """Get a specific Nostr profile by its public key with validation."""
    try:
        # Validate pubkey format
        validated_pubkey = InputValidator.validate_pubkey(pubkey)
        logger.info("Profile lookup", pubkey=validated_pubkey[:8] + "...")

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

            logger.info("Profile found", pubkey=validated_pubkey[:8] + "...")
            return {"success": True, "profile": Profile(**sanitized_data)}
        else:
            logger.info("Profile not found", pubkey=validated_pubkey[:8] + "...")
            raise HTTPException(status_code=404, detail="Profile not found")
    except ValueError as e:
        logger.warning("Invalid pubkey format", pubkey=pubkey, error=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Profile lookup error", error=str(e))
        raise HTTPException(status_code=500, detail="Profile lookup failed")


@app.get(
    "/api/stats",
    response_model=StatsResponse,
    summary="Get Database Statistics",
    dependencies=[Depends(get_authenticated_user)],
)
@rate_limit(requests_per_window=20)  # More restrictive for stats
async def get_profile_stats(req: Request, database: Database = Depends(get_database)):
    """Get statistics about the profile database."""
    try:
        logger.info("Stats request")
        stats = await database.get_profile_stats()
        logger.info("Stats retrieved", total_profiles=stats.get("total_profiles", 0))
        return StatsResponse(success=True, stats=stats)
    except Exception as e:
        logger.error("Stats error", error=str(e))
        raise HTTPException(status_code=500, detail="Stats retrieval failed")


@app.get(
    "/api/business_types",
    summary="Get Available Business Types",
    dependencies=[Depends(get_authenticated_user)],
)
@rate_limit(requests_per_window=20)
async def get_business_types(req: Request, database: Database = Depends(get_database)):
    """Get the list of available business types."""
    try:
        business_types = await database.get_business_types()
        return {
            "success": True,
            "business_types": business_types,
            "count": len(business_types),
        }
    except Exception as e:
        logger.error("Business types error", error=str(e))
        raise HTTPException(status_code=500, detail="Business types retrieval failed")


@app.post(
    "/api/refresh",
    response_model=RefreshResponse,
    summary="Refresh Database",
    dependencies=[Depends(get_authenticated_user)],
)
@rate_limit(requests_per_window=2)  # Very restrictive for expensive operations
async def refresh_profiles_from_nostr(
    req: Request, database: Database = Depends(get_database)
):
    """Manually trigger a refresh of the database."""
    try:
        logger.info("Manual refresh triggered")

        # Import refresh functionality
        from nostr_profiles_mcp_server import refresh_database

        await refresh_database()

        stats = await database.get_profile_stats()
        logger.info("Manual refresh completed", stats=stats)

        return RefreshResponse(
            success=True, message="Database refresh completed", current_stats=stats
        )
    except Exception as e:
        logger.error("Manual refresh error", error=str(e))
        raise HTTPException(status_code=500, detail="Refresh failed")


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(
        "Unhandled exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )

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
    logger.info(
        "Starting Secure Nostr Profiles API",
        environment=SECURITY_CONFIG["ENVIRONMENT"],
        auth_enabled=bool(
            SECURITY_CONFIG["API_KEY"] or SECURITY_CONFIG["BEARER_TOKEN"]
        ),
    )

    # Initialize database
    await get_database()


@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown."""
    logger.info("Shutting down Secure Nostr Profiles API")
    if db:
        await db.close()


if __name__ == "__main__":
    # Production server configuration
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    workers = int(os.getenv("WORKERS", "1"))
    log_level = os.getenv("LOG_LEVEL", "info").lower()

    logger.info("Starting server", host=host, port=port, workers=workers)

    # Production uvicorn configuration
    uvicorn.run(
        "secure_openai_api_server:app",
        host=host,
        port=port,
        workers=workers,
        log_level=log_level,
        access_log=os.getenv("ENABLE_ACCESS_LOGS", "true").lower() == "true",
        server_header=False,  # Hide server info
        date_header=False,  # Hide date header
        reload=False,  # Disable reload in production
    )
