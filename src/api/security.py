"""Simplified security module for Nostr Market MCP server.

Basic security features using only standard library dependencies.
"""

import hashlib
import hmac
import html
import logging
import os
import re
import secrets
import time
from typing import Dict, List, Optional, Set

from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


# Security configuration - load dynamically to allow runtime env var changes
def get_security_config():
    """Get security configuration, loading fresh from environment."""
    return {
        "API_KEY": os.getenv("API_KEY", ""),
        "BEARER_TOKEN": os.getenv("BEARER_TOKEN", ""),
        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "ALLOWED_ORIGINS": (
            os.getenv("ALLOWED_ORIGINS", "").split(",")
            if os.getenv("ALLOWED_ORIGINS")
            else []
        ),
        "ENVIRONMENT": os.getenv("ENVIRONMENT", "development"),
        "RATE_LIMIT_REQUESTS": int(os.getenv("RATE_LIMIT_REQUESTS", "100")),
        "RATE_LIMIT_WINDOW": int(os.getenv("RATE_LIMIT_WINDOW", "60")),
    }


# Backward compatibility
SECURITY_CONFIG = get_security_config()


class SecurityError(HTTPException):
    """Custom security exception."""

    pass


class AuthenticationScheme:
    """Authentication scheme handler."""

    def __init__(self):
        self.security = HTTPBearer(auto_error=False)
        # Load config fresh each time to support runtime env var changes
        self._load_config()

    def _load_config(self):
        """Load fresh configuration from environment variables."""
        config = get_security_config()
        self.api_key = config["API_KEY"]
        self.bearer_token = config["BEARER_TOKEN"]
        self.openai_api_key = config["OPENAI_API_KEY"]

        # Validate configuration in production
        if config["ENVIRONMENT"] == "production":
            if not self.api_key or len(self.api_key) < 32:
                raise ValueError(
                    "API_KEY must be set and at least 32 characters in production"
                )
            if not self.bearer_token or len(self.bearer_token) < 32:
                raise ValueError(
                    "BEARER_TOKEN must be set and at least 32 characters in production"
                )
        elif not self.api_key and not self.bearer_token:
            logger.warning(
                "No authentication configured - API will be open to all requests"
            )

    async def verify_api_key(self, request: Request) -> bool:
        """Verify API key from header or query parameter."""
        # Refresh config to pick up runtime changes
        self._load_config()

        if not self.api_key:
            return True  # No API key required

        # Check header
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            # Check query parameter as fallback
            api_key = request.query_params.get("api_key")

        if not api_key:
            raise SecurityError(status_code=401, detail="API key required")

        # Constant time comparison to prevent timing attacks
        if not hmac.compare_digest(api_key, self.api_key):
            raise SecurityError(status_code=401, detail="Invalid API key")

        return True

    async def verify_bearer_token(
        self, credentials: Optional[HTTPAuthorizationCredentials]
    ) -> bool:
        """Verify bearer token from Authorization header."""
        if not self.bearer_token:
            return True  # No bearer token required

        if not credentials:
            raise SecurityError(status_code=401, detail="Bearer token required")

        # Constant time comparison to prevent timing attacks
        if not hmac.compare_digest(credentials.credentials, self.bearer_token):
            raise SecurityError(status_code=401, detail="Invalid bearer token")

        return True

    async def verify_chat_authentication(self, request: Request) -> tuple[bool, str]:
        """Verify both API key and OpenAI key for chat endpoint."""
        # Refresh config to pick up runtime changes
        self._load_config()

        # Check API key
        if not self.api_key:
            raise SecurityError(
                status_code=401, detail="API key required for chat endpoint"
            )

        api_key = request.headers.get("X-API-Key")
        if not api_key:
            # Check query parameter as fallback
            api_key = request.query_params.get("api_key")

        if not api_key:
            raise SecurityError(status_code=401, detail="API key required")

        # Constant time comparison to prevent timing attacks
        if not hmac.compare_digest(api_key, self.api_key):
            raise SecurityError(status_code=401, detail="Invalid API key")

        # Check OpenAI key
        if not self.openai_api_key:
            raise SecurityError(status_code=500, detail="OpenAI API key not configured")

        return True, self.openai_api_key


# Global authentication instance
auth = AuthenticationScheme()


# Input validation using standard library
class InputValidator:
    """Input validation and sanitization using standard library."""

    @staticmethod
    def sanitize_string(value: str, max_length: int = 1000) -> str:
        """Sanitize and validate string input."""
        if not isinstance(value, str):
            raise ValueError("Input must be a string")

        # Trim whitespace
        value = value.strip()

        # Check length
        if len(value) > max_length:
            raise ValueError(f"Input too long (max {max_length} characters)")

        # Escape HTML to prevent XSS
        value = html.escape(value)

        return value

    @staticmethod
    def validate_pubkey(pubkey: str) -> str:
        """Validate Nostr public key format."""
        pubkey = InputValidator.sanitize_string(pubkey, max_length=64)

        # Must be hex string of 64 characters
        if len(pubkey) != 64:
            raise ValueError("Public key must be 64 characters")

        if not re.match(r"^[0-9a-fA-F]{64}$", pubkey):
            raise ValueError("Public key must be a valid hex string")

        return pubkey.lower()

    @staticmethod
    def validate_search_query(query: str) -> str:
        """Validate search query."""
        query = InputValidator.sanitize_string(query, max_length=200)

        if len(query) < 1:
            raise ValueError("Search query cannot be empty")

        # Remove potential SQL injection patterns
        dangerous_patterns = ["'", '"', ";", "--", "/*", "*/", "xp_", "sp_"]
        for pattern in dangerous_patterns:
            if pattern.lower() in query.lower():
                raise ValueError("Invalid characters in search query")

        return query


# Simple rate limiting using memory
class SimpleRateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self):
        self.requests: Dict[str, List[float]] = {}

    def is_allowed(
        self, client_id: str, max_requests: int = 100, window_seconds: int = 60
    ) -> bool:
        """Check if request is allowed based on rate limits."""
        now = time.time()

        # Clean old requests
        if client_id in self.requests:
            self.requests[client_id] = [
                req_time
                for req_time in self.requests[client_id]
                if now - req_time < window_seconds
            ]
        else:
            self.requests[client_id] = []

        # Check if under limit
        if len(self.requests[client_id]) >= max_requests:
            return False

        # Add current request
        self.requests[client_id].append(now)
        return True


# Global rate limiter
rate_limiter = SimpleRateLimiter()


# Pydantic models with validation
class SecureSearchRequest(BaseModel):
    """Secure search request model."""

    query: str = Field(..., min_length=1, max_length=200)
    limit: int = Field(default=10, ge=1, le=100)

    @field_validator("query")
    @classmethod
    def validate_query(cls, v):
        return InputValidator.validate_search_query(v)


class SecureBusinessSearchRequest(BaseModel):
    """Secure business search request model."""

    query: str = Field(default="", max_length=200)
    business_type: str = Field(..., min_length=1, max_length=50)
    limit: int = Field(default=10, ge=1, le=100)

    @field_validator("query")
    @classmethod
    def validate_query(cls, v):
        if v:
            return InputValidator.validate_search_query(v)
        return v

    @field_validator("business_type")
    @classmethod
    def validate_business_type(cls, v):
        allowed_types = {
            "retail",
            "restaurant",
            "service",
            "business",
            "entertainment",
            "other",
        }
        if v not in allowed_types:
            raise ValueError(
                f"Business type must be one of: {', '.join(sorted(allowed_types))}"
            )
        return v


# Security middleware
class SecurityMiddleware:
    """Security middleware for request processing."""

    def __init__(self):
        self.blocked_ips: Set[str] = set()
        self.suspicious_patterns = [
            "admin",
            "wp-admin",
            "phpmyadmin",
            "config",
            "env",
            "backup",
            "sql",
            "dump",
            "database",
            "passwd",
            "shadow",
            "etc",
            "../",
            "..\\",
            "%2e%2e",
            "script",
            "javascript",
            "vbscript",
        ]

    async def process_request(self, request: Request) -> None:
        """Process incoming request for security checks."""
        client_ip = self.get_client_ip(request)

        # Check if IP is blocked
        if client_ip in self.blocked_ips:
            raise SecurityError(status_code=403, detail="IP address blocked")

        # Check for suspicious patterns in URL
        url_path = str(request.url.path).lower()
        for pattern in self.suspicious_patterns:
            if pattern in url_path:
                logger.warning(f"Suspicious request from {client_ip}: {url_path}")

        # Check user agent
        user_agent = request.headers.get("user-agent", "").lower()
        if not user_agent or len(user_agent) < 10:
            logger.warning(f"Suspicious user agent from {client_ip}: {user_agent}")

    def get_client_ip(self, request: Request) -> str:
        """Get client IP from request."""
        # Check for forwarded headers (load balancer)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        forwarded = request.headers.get("X-Forwarded")
        if forwarded:
            return forwarded.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to direct connection
        return request.client.host if request.client else "unknown"

    def block_ip(self, ip: str) -> None:
        """Block an IP address."""
        self.blocked_ips.add(ip)
        logger.warning(f"Blocked IP address: {ip}")

    def unblock_ip(self, ip: str) -> None:
        """Unblock an IP address."""
        self.blocked_ips.discard(ip)
        logger.info(f"Unblocked IP address: {ip}")


# Global security middleware instance
security_middleware = SecurityMiddleware()


# Chat request models
class ChatMessage(BaseModel):
    """Chat message model."""

    role: str = Field(
        ..., description="Role of the message sender (user, assistant, system)"
    )
    content: str = Field(..., description="Content of the message")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        if v not in ["user", "assistant", "system"]:
            raise ValueError("Role must be 'user', 'assistant', or 'system'")
        return v

    @field_validator("content")
    @classmethod
    def validate_content(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Message content cannot be empty")
        if len(v) > 10000:
            raise ValueError("Message content too long (max 10000 characters)")
        return v.strip()


class SecureChatRequest(BaseModel):
    """Secure chat request model."""

    messages: List[ChatMessage] = Field(..., description="List of chat messages")
    stream: bool = Field(default=True, description="Whether to stream the response")
    max_tokens: Optional[int] = Field(
        default=1000, description="Maximum tokens to generate"
    )
    temperature: Optional[float] = Field(
        default=0.7, description="Sampling temperature"
    )

    @field_validator("messages")
    @classmethod
    def validate_messages(cls, v):
        if not v:
            raise ValueError("At least one message is required")
        if len(v) > 50:
            raise ValueError("Too many messages (max 50)")
        return v

    @field_validator("max_tokens")
    @classmethod
    def validate_max_tokens(cls, v):
        if v is not None and (v < 1 or v > 4000):
            raise ValueError("max_tokens must be between 1 and 4000")
        return v

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v):
        if v is not None and (v < 0 or v > 2):
            raise ValueError("temperature must be between 0 and 2")
        return v


# Security headers
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}


# Utility functions
def generate_api_key(length: int = 32) -> str:
    """Generate a secure API key."""
    return secrets.token_urlsafe(length)


def generate_bearer_token(length: int = 32) -> str:
    """Generate a secure bearer token."""
    return secrets.token_urlsafe(length)


def hash_password(password: str, salt: Optional[bytes] = None) -> tuple[str, bytes]:
    """Hash a password with salt."""
    if salt is None:
        salt = secrets.token_bytes(32)

    pwdhash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000)
    return pwdhash.hex(), salt


def verify_password(password: str, hashed: str, salt: bytes) -> bool:
    """Verify a password against its hash."""
    pwdhash, _ = hash_password(password, salt)
    return hmac.compare_digest(pwdhash, hashed)


if __name__ == "__main__":
    # Generate new credentials for setup
    print("Generated API Key:", generate_api_key())
    print("Generated Bearer Token:", generate_bearer_token())
