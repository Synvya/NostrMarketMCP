#!/usr/bin/env python3
"""
Run the API server with the reorganized code structure.
"""

import os
import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Set up environment variables for local development
os.environ.update(
    {
        # Security settings - safe for local testing
        "API_KEY": "local_test_api_key",
        "BEARER_TOKEN": "local_test_bearer_token",
        "ALLOWED_ORIGINS": "http://localhost:3000,http://127.0.0.1:3000",
        "ENVIRONMENT": "development",
        # Rate limiting - more permissive for testing
        "RATE_LIMIT_REQUESTS": "1000",
        "RATE_LIMIT_WINDOW": "60",
        # Database - local file
        "DATABASE_PATH": "./local_test.db",
        # Nostr relays
        "NOSTR_RELAYS": "wss://relay.damus.io,wss://nos.lol,wss://relay.snort.social,wss://nostr.wine,wss://relay.nostr.band",
        # Logging
        "LOG_LEVEL": "debug",
        "ENABLE_ACCESS_LOGS": "true",
        # Server
        "HOST": "127.0.0.1",
        "PORT": "8080",
        "WORKERS": "1",
    }
)

import uvicorn


def main():
    """Run the local development server."""
    print("🚀 Starting local development server...")
    print(f"📊 API will be available at: http://127.0.0.1:8080")
    print(f"📖 API docs at: http://127.0.0.1:8080/docs")
    print(f"🔑 API Key for testing: {os.environ['API_KEY']}")
    print(f"💾 Database: {os.environ['DATABASE_PATH']}")
    print()
    print("Press Ctrl+C to stop the server")
    print("-" * 50)

    # Run the server with import string for reload to work
    uvicorn.run(
        "api.simple_secure_server:app",
        host="127.0.0.1",
        port=8080,
        reload=True,  # Auto-reload on code changes
        log_level="debug",
    )


if __name__ == "__main__":
    main()
