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

import openai
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from src.core import Database
from src.core.shared_database import get_shared_database
from src.mcp.server import cleanup_db, initialize_db, refresh_database

from .security import (
    SECURITY_CONFIG,
    SECURITY_HEADERS,
    ChatMessage,
    InputValidator,
    SecureBusinessSearchRequest,
    SecureChatRequest,
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
    # Get fresh config to check what's actually configured
    from .security import get_security_config

    current_config = get_security_config()

    # If no authentication is configured, allow access
    if not current_config["API_KEY"] and not current_config["BEARER_TOKEN"]:
        return True

    api_key_valid = False
    bearer_token_valid = False

    # Try API key authentication
    if current_config["API_KEY"]:
        try:
            await auth.verify_api_key(request)
            api_key_valid = True
        except Exception as e:
            logger.debug(f"API key authentication failed: {e}")

    # Try Bearer token authentication
    if current_config["BEARER_TOKEN"]:
        try:
            await auth.verify_bearer_token(credentials)
            bearer_token_valid = True
        except Exception as e:
            logger.debug(f"Bearer token authentication failed: {e}")

    # If either authentication method succeeded, allow access
    if api_key_valid or bearer_token_valid:
        return True

    # If both methods are configured but both failed, raise error
    if current_config["API_KEY"] and current_config["BEARER_TOKEN"]:
        raise HTTPException(
            status_code=401, detail="Valid API key or Bearer token required"
        )
    elif current_config["API_KEY"]:
        raise HTTPException(status_code=401, detail="Valid API key required")
    elif current_config["BEARER_TOKEN"]:
        raise HTTPException(status_code=401, detail="Valid Bearer token required")
    else:
        # No authentication configured
        return True


# Database dependency
async def get_database() -> Database:
    """Get shared database instance."""
    return await get_shared_database()


# Chat authentication dependency
async def get_chat_authenticated_user(request: Request) -> str:
    """Verify authentication for chat endpoint and return OpenAI API key."""
    try:
        is_valid, openai_api_key = await auth.verify_chat_authentication(request)
        return openai_api_key
    except Exception as e:
        logger.debug(f"Chat authentication failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))


# OpenAI client helper
def get_openai_client(api_key: str) -> openai.OpenAI:
    """Get OpenAI client with API key."""
    return openai.OpenAI(api_key=api_key)


# Chat service for LLM integration
class ChatService:
    """Service to handle chat interactions with OpenAI and profile searches."""

    def __init__(self, openai_client: openai.OpenAI, database: Database):
        self.client = openai_client
        self.database = database

        # Define available functions for OpenAI
        self.functions = [
            {
                "name": "search_profiles",
                "description": "Search for Nostr profiles by content including names, descriptions, hashtags, and locations",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for profile content",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (1-50)",
                            "minimum": 1,
                            "maximum": 50,
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "search_business_profiles",
                "description": "Search for business profiles filtered by business type",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for business content",
                        },
                        "business_type": {
                            "type": "string",
                            "enum": [
                                "retail",
                                "restaurant",
                                "service",
                                "business",
                                "entertainment",
                                "other",
                            ],
                            "description": "Business type to filter by",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results (1-50)",
                            "minimum": 1,
                            "maximum": 50,
                            "default": 10,
                        },
                    },
                    "required": ["business_type"],
                },
            },
            {
                "name": "get_profile_by_pubkey",
                "description": "Get a specific profile by its public key",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pubkey": {
                            "type": "string",
                            "description": "64-character hex public key",
                        }
                    },
                    "required": ["pubkey"],
                },
            },
            {
                "name": "get_business_types",
                "description": "Get list of available business types",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "get_stats",
                "description": "Get database statistics",
                "parameters": {"type": "object", "properties": {}},
            },
        ]

    def _deduplicate_profiles(self, profiles: List[dict]) -> List[dict]:
        """
        Remove duplicate profiles, preferring production environment over demo.
        Identifies duplicates by matching display_name, name, or website.
        """
        if not profiles:
            return profiles

        # Group profiles by potential duplicate keys
        profile_groups = {}

        for profile in profiles:
            # Create a key for identifying potential duplicates
            # Use display_name, name, or website as duplicate detection criteria
            duplicate_key = None

            if profile.get("display_name"):
                duplicate_key = profile["display_name"].lower().strip()
            elif profile.get("name"):
                duplicate_key = profile["name"].lower().strip()
            elif profile.get("website"):
                duplicate_key = profile["website"].lower().strip()
            else:
                # If no identifying info, use pubkey (unique anyway)
                duplicate_key = profile.get("pubkey", "")

            if duplicate_key:
                if duplicate_key not in profile_groups:
                    profile_groups[duplicate_key] = []
                profile_groups[duplicate_key].append(profile)

        # For each group, prefer production over demo environment
        deduplicated = []
        for group in profile_groups.values():
            if len(group) == 1:
                deduplicated.append(group[0])
            else:
                # Multiple profiles found - prefer production over demo
                production_profiles = [
                    p for p in group if p.get("environment") == "production"
                ]
                demo_profiles = [p for p in group if p.get("environment") == "demo"]
                other_profiles = [
                    p
                    for p in group
                    if p.get("environment") not in ["production", "demo"]
                ]

                if production_profiles:
                    # Use first production profile
                    deduplicated.append(production_profiles[0])
                elif other_profiles:
                    # Use first non-demo profile if no production
                    deduplicated.append(other_profiles[0])
                elif demo_profiles:
                    # Only use demo if that's all we have
                    deduplicated.append(demo_profiles[0])
                else:
                    # Fallback to first profile
                    deduplicated.append(group[0])

        return deduplicated

    async def call_function(self, function_name: str, arguments: dict) -> dict:
        """Execute a function call and return results."""
        try:
            if function_name == "search_profiles":
                query = arguments.get("query", "")
                limit = arguments.get("limit", 10)
                profiles = await self.database.search_profiles(query)
                # Apply deduplication before limiting results
                deduplicated_profiles = self._deduplicate_profiles(profiles)
                limited_profiles = deduplicated_profiles[:limit]
                return {
                    "success": True,
                    "count": len(limited_profiles),
                    "profiles": limited_profiles,
                    "query": query,
                }

            elif function_name == "search_business_profiles":
                query = arguments.get("query", "")
                business_type = arguments.get("business_type")
                limit = arguments.get("limit", 10)
                profiles = await self.database.search_business_profiles(
                    query, business_type
                )
                # Apply deduplication before limiting results
                deduplicated_profiles = self._deduplicate_profiles(profiles)
                limited_profiles = deduplicated_profiles[:limit]
                return {
                    "success": True,
                    "count": len(limited_profiles),
                    "profiles": limited_profiles,
                    "query": query,
                    "business_type": business_type,
                }

            elif function_name == "get_profile_by_pubkey":
                pubkey = arguments.get("pubkey")
                validated_pubkey = InputValidator.validate_pubkey(pubkey)
                resource_uri = f"nostr://{validated_pubkey}/profile"
                profile = await self.database.get_resource_data(resource_uri)
                if profile:
                    profile["pubkey"] = validated_pubkey
                    return {"success": True, "profile": profile}
                else:
                    return {"success": False, "error": "Profile not found"}

            elif function_name == "get_business_types":
                business_types = await self.database.get_business_types()
                return {
                    "success": True,
                    "business_types": business_types,
                    "count": len(business_types),
                }

            elif function_name == "get_stats":
                stats = await self.database.get_profile_stats()
                return {"success": True, "stats": stats}

            else:
                return {"success": False, "error": f"Unknown function: {function_name}"}

        except Exception as e:
            logger.error(f"Function call error for {function_name}: {e}")
            return {"success": False, "error": str(e)}

    async def chat_stream(
        self,
        messages: List[ChatMessage],
        max_tokens: int = 1000,
        temperature: float = 0.7,
    ):
        """Handle streaming chat with OpenAI and function calling."""
        try:
            # Convert messages to OpenAI format
            openai_messages = [
                {"role": msg.role, "content": msg.content} for msg in messages
            ]

            # Add system message if not present
            if not openai_messages or openai_messages[0]["role"] != "system":
                system_message = {
                    "role": "system",
                    "content": """You are a helpful shopping assistant. You help people find businesses, products, and services from a database that contains business information.

You have access to a business directory database with comprehensive business profiles. You can:
- Search broadly for businesses using api/search
- Search businesses filtered by specific business type using api/search_by_business_type
- Get detailed business information using api/profile/<public-key>
- Get all available business categories using api/business_types
- Get database statistics using api/stats
- Refresh the database with latest business information using api/refresh_database

When users ask about finding businesses, products, or services, use the appropriate search functions to help them. Be helpful, accurate, and provide relevant results. If search results are empty, suggest alternative search terms or broader categories.

Available business types: retail, restaurant, service, business, entertainment, other

Important: If you find duplicate entries for the same business, only present one of them to the user. If duplicate entries exist where one has environment="demo" and another has environment="production", always present the "production" entry and ignore the "demo" entry.""",
                }
                openai_messages.insert(0, system_message)

            # Make initial request to OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=openai_messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
                functions=self.functions,
                function_call="auto",
            )

            # Process streaming response
            function_call_buffer = {"name": "", "arguments": ""}
            collecting_function_call = False

            for chunk in response:
                if chunk.choices[0].delta.function_call:
                    # Handle function calling
                    collecting_function_call = True
                    func_call = chunk.choices[0].delta.function_call

                    if func_call.name:
                        function_call_buffer["name"] += func_call.name
                    if func_call.arguments:
                        function_call_buffer["arguments"] += func_call.arguments

                elif (
                    collecting_function_call
                    and chunk.choices[0].finish_reason == "function_call"
                ):
                    # Execute function call
                    try:
                        function_name = function_call_buffer["name"]
                        arguments = json.loads(function_call_buffer["arguments"])

                        logger.info(
                            f"Executing function: {function_name} with args: {arguments}"
                        )

                        function_result = await self.call_function(
                            function_name, arguments
                        )

                        # Add function result to conversation and continue
                        openai_messages.append(
                            {
                                "role": "assistant",
                                "content": None,
                                "function_call": {
                                    "name": function_name,
                                    "arguments": function_call_buffer["arguments"],
                                },
                            }
                        )
                        openai_messages.append(
                            {
                                "role": "function",
                                "name": function_name,
                                "content": json.dumps(function_result),
                            }
                        )

                        # Continue conversation with function result
                        follow_up_response = self.client.chat.completions.create(
                            model="gpt-4",
                            messages=openai_messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                            stream=True,
                        )

                        for follow_chunk in follow_up_response:
                            if follow_chunk.choices[0].delta.content:
                                content = follow_chunk.choices[0].delta.content
                                yield f"data: {json.dumps({'content': content})}\n\n"

                    except Exception as e:
                        logger.error(f"Function execution error: {e}")
                        error_msg = f"Error executing search: {str(e)}"
                        yield f"data: {json.dumps({'content': error_msg})}\n\n"

                    # Reset function call buffer
                    function_call_buffer = {"name": "", "arguments": ""}
                    collecting_function_call = False

                elif chunk.choices[0].delta.content and not collecting_function_call:
                    # Regular content streaming
                    content = chunk.choices[0].delta.content
                    yield f"data: {json.dumps({'content': content})}\n\n"

            # Send completion marker
            yield f"data: {json.dumps({'done': True})}\n\n"

        except Exception as e:
            logger.error(f"Chat stream error: {e}")
            error_msg = f"Chat error: {str(e)}"
            yield f"data: {json.dumps({'error': error_msg})}\n\n"


# Dynamic dependency helper
def get_auth_dependencies():
    """Get authentication dependencies based on current config."""
    from .security import get_security_config

    current_config = get_security_config()
    if current_config["API_KEY"] or current_config["BEARER_TOKEN"]:
        return [Depends(get_authenticated_user)]
    return []


# Response models
class Profile(BaseModel):
    """Profile model with validation - includes full profile data."""

    pubkey: str = Field(..., description="Public key of the profile")
    name: Optional[str] = Field(None, description="Display name")
    display_name: Optional[str] = Field(None, description="Display name (alternative)")
    about: Optional[str] = Field(None, description="Profile description")
    picture: Optional[str] = Field(None, description="Profile picture URL")
    banner: Optional[str] = Field(None, description="Profile banner URL")
    nip05: Optional[str] = Field(None, description="NIP-05 verification")
    website: Optional[str] = Field(None, description="Website URL")
    lud06: Optional[str] = Field(None, description="Lightning address (LNURL)")
    lud16: Optional[str] = Field(None, description="Lightning address")
    business_type: Optional[str] = Field(
        None, description="Business type if applicable"
    )
    tags: Optional[List] = Field(None, description="Nostr event tags")
    created_at: Optional[int] = Field(None, description="Profile creation timestamp")

    class Config:
        extra = "allow"  # Allow additional fields from the profile content


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
    "/api/search",
    response_model=SearchResponse,
    summary="Search Profiles",
    dependencies=[Depends(get_authenticated_user)],
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
    "/api/search_by_business_type",
    response_model=SearchResponse,
    summary="Search Business Profiles",
    dependencies=get_auth_dependencies(),
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
            request.business_type,
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
    dependencies=get_auth_dependencies(),
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
    dependencies=get_auth_dependencies(),
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
    dependencies=get_auth_dependencies(),
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
    dependencies=get_auth_dependencies(),
)
async def refresh_profiles_from_nostr(database: Database = Depends(get_database)):
    """Manually trigger a refresh of the database."""
    try:
        logger.info("Manual refresh triggered")

        await refresh_database()

        stats = await database.get_profile_stats()
        logger.info(f"Manual refresh completed: {stats}")

        return RefreshResponse(
            success=True, message="Database refresh completed", current_stats=stats
        )
    except Exception as e:
        logger.error(f"Manual refresh error: {e}")
        raise HTTPException(status_code=500, detail="Refresh failed")


@app.post(
    "/api/chat",
    summary="Chat with AI Assistant",
    description="Stream chat responses from AI assistant with access to profile search functions",
)
async def chat_with_assistant(
    request: SecureChatRequest,
    openai_api_key: str = Depends(get_chat_authenticated_user),
    database: Database = Depends(get_database),
):
    """Stream chat responses from AI assistant with profile search capabilities."""
    try:
        logger.info(
            f"Chat request: {len(request.messages)} messages, stream={request.stream}"
        )

        # Create OpenAI client and chat service
        openai_client = get_openai_client(openai_api_key)
        chat_service = ChatService(openai_client, database)

        # Return streaming response
        if request.stream:
            return StreamingResponse(
                chat_service.chat_stream(
                    request.messages,
                    max_tokens=request.max_tokens or 1000,
                    temperature=request.temperature or 0.7,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                },
            )
        else:
            # Non-streaming response (for compatibility)
            response_content = ""
            async for chunk in chat_service.chat_stream(
                request.messages,
                max_tokens=request.max_tokens or 1000,
                temperature=request.temperature or 0.7,
            ):
                if chunk.startswith("data: "):
                    try:
                        chunk_data = json.loads(chunk[6:].strip())
                        if chunk_data.get("content"):
                            response_content += chunk_data["content"]
                        elif chunk_data.get("done"):
                            break
                        elif chunk_data.get("error"):
                            raise HTTPException(
                                status_code=500, detail=chunk_data["error"]
                            )
                    except json.JSONDecodeError:
                        continue

            return {
                "success": True,
                "message": {"role": "assistant", "content": response_content},
                "stream": False,
            }

    except Exception as e:
        logger.error(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


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

    # Start automatic refresh every hour (unless disabled for testing)
    if not os.getenv("DISABLE_BACKGROUND_TASKS"):
        try:
            await initialize_db()
            logger.info(
                "Automatic refresh enabled: profiles will be refreshed every hour"
            )
        except Exception as e:
            logger.warning(f"Failed to enable automatic refresh: {e}")
            logger.info("Manual refresh will still be available via /api/refresh")
    else:
        logger.info(
            "Background tasks disabled - skipping automatic refresh initialization"
        )


@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown."""
    logger.info("Shutting down Secure Nostr Profiles API")

    # Stop automatic refresh (if it was started)
    if not os.getenv("DISABLE_BACKGROUND_TASKS"):
        try:
            await cleanup_db()
            logger.info("Automatic refresh stopped")
        except Exception as e:
            logger.warning(f"Error stopping automatic refresh: {e}")
    else:
        logger.info("Background tasks were disabled - no cleanup needed")

    # Close database
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
        "src.api.server:app",
        host=host,
        port=port,
        log_level=log_level,
        access_log=True,
        reload=False,
    )
