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
from typing import Any, Dict, List, Optional, Union

import structlog
import uvicorn
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, computed_field
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from synvya_sdk import Namespace, Profile, ProfileType

from nostr_market_mcp.db import Database
from nostr_profiles_mcp_server import refresh_database, set_shared_database
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

# Load environment variables
load_dotenv()

# Import our security module and database
sys.path.insert(0, str(Path(__file__).parent))


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
        db = await initialize_database()
    return db


async def initialize_database():
    """Initialize the database."""
    db = Database(DEFAULT_DB_PATH)
    await db.initialize()
    logger.info(f"Database initialized: {DEFAULT_DB_PATH}")

    # Share the database instance with the MCP server
    set_shared_database(db)

    return db


# Pydantic models for responses
class ProfileResponse(Profile):
    """Extended Profile response with computed fields for business_type and tags"""

    @computed_field
    @property
    def business_type(self) -> Optional[str]:
        """Extract business type from profile_type"""
        return self.profile_type.value if self.profile_type else None

    @computed_field
    @property
    def tags(self) -> List[List[str]]:
        """Generate tags from profile data"""
        tags = []

        # Add profile type tag if present
        if self.profile_type and self.profile_type != ProfileType.OTHER:
            tags.append(["L", Namespace.BUSINESS_TYPE.value])  # ["L", "business.type"]
            tags.append(["l", self.profile_type.value])  # ["l", "retail"]

        return tags


class SearchResponse(BaseModel):
    """Response model for search endpoints"""

    profiles: List[ProfileResponse]
    count: int


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


@app.get("/search", response_model=SearchResponse)
@rate_limit("10/minute")
async def search_profiles(
    query: SecureSearchRequest = Depends(),
    token: HTTPAuthorizationCredentials = Depends(auth),
) -> SearchResponse:
    """Search for business profiles with authentication and rate limiting"""
    logger.info(f"Search request for query: {query.q}")

    try:
        profiles_data = await db.search_profiles(query.q, limit=query.limit or 50)
        profiles = [_convert_profile_data(data) for data in profiles_data]

        logger.debug(f"Search found {len(profiles)} profiles")
        return SearchResponse(profiles=profiles, count=len(profiles))
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail="Search failed")


@app.get("/search/business/{business_type}", response_model=SearchResponse)
@rate_limit("10/minute")
async def search_by_business_type(
    business_type: str,
    query: SecureBusinessSearchRequest = Depends(),
    token: HTTPAuthorizationCredentials = Depends(auth),
) -> SearchResponse:
    """Search for profiles by business type with authentication and rate limiting"""
    logger.info(f"Business search request for type: {business_type}")

    try:
        # Validate business type against ProfileType enum values
        valid_types = [pt.value for pt in ProfileType]
        if business_type not in valid_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid business type. Must be one of: {', '.join(valid_types)}",
            )

        profiles_data = await db.search_by_business_type(
            business_type, limit=query.limit or 50
        )
        profiles = [_convert_profile_data(data) for data in profiles_data]

        logger.debug(f"Business search found {len(profiles)} profiles")
        return SearchResponse(profiles=profiles, count=len(profiles))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Business search error: {e}")
        raise HTTPException(status_code=500, detail="Search failed")


@app.get("/profile/{public_key}", response_model=ProfileResponse)
@rate_limit("20/minute")
async def get_profile(
    public_key: str,
    token: HTTPAuthorizationCredentials = Depends(auth),
) -> ProfileResponse:
    """Get a specific profile by public key with authentication and rate limiting"""
    logger.info(f"Profile request for public_key: {public_key[:8]}...")

    try:
        # Validate public key format (hex, 64 characters)
        if not public_key or len(public_key) != 64:
            raise HTTPException(
                status_code=400, detail="Public key must be 64 characters"
            )

        try:
            int(public_key, 16)  # Validate hex format
        except ValueError:
            raise HTTPException(status_code=400, detail="Public key must be valid hex")

        resource_uri = f"nostr://{public_key}/profile"
        profile_data = await db.get_resource_data(resource_uri)

        if not profile_data:
            raise HTTPException(status_code=404, detail="Profile not found")

        profile = _convert_profile_data(profile_data)
        logger.debug(f"Retrieved profile for {public_key[:8]}...")
        return profile
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get profile error: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve profile")


@app.get(
    "/api/stats",
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
        return {"success": True, "stats": stats}
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


@app.post("/refresh")
@rate_limit("1/minute")
async def refresh_profiles(
    token: HTTPAuthorizationCredentials = Depends(auth),
) -> dict:
    """Refresh profile database with authentication and rate limiting"""
    logger.info("Database refresh request")

    try:
        result = await refresh_database()
        logger.info(f"Database refresh completed: {result}")
        return {"message": "Database refreshed successfully", "result": result}
    except Exception as e:
        logger.error(f"Refresh error: {e}")
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


def _convert_profile_data(data: Dict[str, Any]) -> ProfileResponse:
    """Convert database profile data to ProfileResponse object"""
    # Convert profile_type string back to ProfileType enum
    profile_type = None
    if data.get("profile_type"):
        try:
            # Find the enum by value
            for pt in ProfileType:
                if pt.value == data["profile_type"]:
                    profile_type = pt
                    break
        except Exception:
            profile_type = ProfileType.OTHER

    if not profile_type:
        profile_type = ProfileType.OTHER

    # Create ProfileResponse with all synvya-sdk Profile fields
    return ProfileResponse(
        public_key=data.get("public_key", ""),
        display_name=data.get("display_name"),
        name=data.get("name"),
        about=data.get("about"),
        picture=data.get("picture"),
        banner=data.get("banner"),
        nip05=data.get("nip05"),
        website=data.get("website"),
        email=data.get("email"),
        phone=data.get("phone"),
        street=data.get("street"),
        city=data.get("city"),
        state=data.get("state"),
        zip_code=data.get("zip_code"),
        country=data.get("country"),
        hashtags=data.get("hashtags", []),
        locations=data.get("locations", []),
        bot=data.get("bot", False),
        nip05_validated=data.get("nip05_validated", False),
        namespace=data.get("namespace", ""),
        profile_type=profile_type,
        created_at=data.get("created_at"),
    )


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
