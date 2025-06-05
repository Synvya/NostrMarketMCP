"""Security module for Nostr Market MCP server.

Provides authentication, rate limiting, input validation, and security middleware.
"""

import hashlib
import hmac
import logging
import os
import secrets
import time
from typing import Dict, List, Optional, Set

import bleach
from fastapi import HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

# Security configuration
SECURITY_CONFIG = {
    "API_KEY": os.getenv("API_KEY", ""),
    "BEARER_TOKEN": os.getenv("BEARER_TOKEN", ""),
    "ALLOWED_ORIGINS": (
        os.getenv("ALLOWED_ORIGINS", "").split(",")
        if os.getenv("ALLOWED_ORIGINS")
        else []
    ),
    "ENVIRONMENT": os.getenv("ENVIRONMENT", "development"),
    "RATE_LIMIT_REQUESTS": int(os.getenv("RATE_LIMIT_REQUESTS", "100")),
    "RATE_LIMIT_WINDOW": int(os.getenv("RATE_LIMIT_WINDOW", "60")),
}

# Rate limiter
limiter = Limiter(key_func=get_remote_address)


class SecurityError(HTTPException):
    """Custom security exception."""

    pass


class AuthenticationScheme:
    """Authentication scheme handler."""

    def __init__(self):
        self.security = HTTPBearer(auto_error=False)
        self.api_key = SECURITY_CONFIG["API_KEY"]
        self.bearer_token = SECURITY_CONFIG["BEARER_TOKEN"]

        # Validate configuration in production
        if SECURITY_CONFIG["ENVIRONMENT"] == "production":
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


# Global authentication instance
auth = AuthenticationScheme()


# Input validation
class InputValidator:
    """Input validation and sanitization."""

    # Allowed HTML tags and attributes for content sanitization
    ALLOWED_TAGS = []  # No HTML tags allowed
    ALLOWED_ATTRIBUTES = {}

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

        # Sanitize HTML/scripts
        value = bleach.clean(
            value,
            tags=InputValidator.ALLOWED_TAGS,
            attributes=InputValidator.ALLOWED_ATTRIBUTES,
            strip=True,
        )

        return value

    @staticmethod
    def validate_pubkey(pubkey: str) -> str:
        """Validate Nostr public key format."""
        pubkey = InputValidator.sanitize_string(pubkey, max_length=64)

        # Must be hex string of 64 characters
        if len(pubkey) != 64:
            raise ValueError("Public key must be 64 characters")

        try:
            int(pubkey, 16)
        except ValueError:
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


# Pydantic models with validation
class SecureSearchRequest(BaseModel):
    """Secure search request model."""

    query: str = Field(..., min_length=1, max_length=200)
    limit: int = Field(default=10, ge=1, le=100)

    @validator("query")
    def validate_query(cls, v):
        return InputValidator.validate_search_query(v)


class SecureBusinessSearchRequest(BaseModel):
    """Secure business search request model."""

    query: str = Field(default="", max_length=200)
    business_type: str = Field(default="", max_length=50)
    limit: int = Field(default=10, ge=1, le=100)

    @validator("query")
    def validate_query(cls, v):
        if v:
            return InputValidator.validate_search_query(v)
        return v

    @validator("business_type")
    def validate_business_type(cls, v):
        if v:
            allowed_types = {
                "retail",
                "restaurant",
                "services",
                "business",
                "entertainment",
                "other",
            }
            if v not in allowed_types:
                raise ValueError(
                    f"Business type must be one of: {', '.join(allowed_types)}"
                )
        return v


# Security middleware
class SecurityMiddleware:
    """Security middleware for request processing."""

    def __init__(self):
        self.blocked_ips: Set[str] = set()
        self.request_counts: Dict[str, List[float]] = {}
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
        client_ip = get_remote_address(request)

        # Check if IP is blocked
        if client_ip in self.blocked_ips:
            raise SecurityError(status_code=403, detail="IP address blocked")

        # Check for suspicious patterns in URL
        url_path = str(request.url.path).lower()
        for pattern in self.suspicious_patterns:
            if pattern in url_path:
                logger.warning(f"Suspicious request from {client_ip}: {url_path}")
                # Could implement auto-blocking here

        # Check user agent
        user_agent = request.headers.get("user-agent", "").lower()
        if not user_agent or len(user_agent) < 10:
            logger.warning(f"Suspicious user agent from {client_ip}: {user_agent}")

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


# Rate limiting decorators
def rate_limit(requests_per_window: Optional[int] = None):
    """Rate limiting decorator."""
    requests = requests_per_window or SECURITY_CONFIG["RATE_LIMIT_REQUESTS"]
    window = SECURITY_CONFIG["RATE_LIMIT_WINDOW"]
    return limiter.limit(f"{requests}/{window}seconds")


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


# Rate limit exceeded handler
def custom_rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """Custom handler for rate limit exceeded."""
    client_ip = get_remote_address(request)
    logger.warning(f"Rate limit exceeded for {client_ip}: {exc.detail}")
    return HTTPException(
        status_code=429,
        detail=f"Rate limit exceeded: {exc.detail}",
        headers={"Retry-After": str(exc.retry_after)},
    )


if __name__ == "__main__":
    # Generate new credentials for setup
    print("Generated API Key:", generate_api_key())
    print("Generated Bearer Token:", generate_bearer_token())
