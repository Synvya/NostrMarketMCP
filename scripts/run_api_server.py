#!/usr/bin/env python3
"""
Run the API server with the reorganized code structure.
"""

import os
import sys
from pathlib import Path

# Resolve project root (one level up from scripts) and add its "src" directory
project_root = Path(__file__).resolve().parent.parent
src_path = project_root / "src"
sys.path.insert(0, str(src_path))

# Ensure child processes (e.g., uvicorn reload) can resolve the same modules
existing_py_path = os.environ.get("PYTHONPATH", "")
if str(src_path) not in existing_py_path.split(os.pathsep):
    os.environ["PYTHONPATH"] = (
        f"{src_path}{os.pathsep}{existing_py_path}"
        if existing_py_path
        else str(src_path)
    )

# Set up default environment variables for local development (only if not already set)
default_env = {
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
    # Server
    "HOST": "127.0.0.1",
    "PORT": "8080",
}

# Only set environment variables if they're not already set
for key, value in default_env.items():
    if key not in os.environ:
        os.environ[key] = value

import uvicorn


def main():
    """Run the local development server."""
    # Get host and port from environment, with defaults
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8080"))
    log_level = os.environ.get("LOG_LEVEL", "debug")

    print("🚀 Starting local development server...")
    print(f"📊 API will be available at: http://{host}:{port}")
    print(f"📖 API docs at: http://{host}:{port}/docs")
    print(f"🔑 API Key for testing: {os.environ['API_KEY']}")
    print(f"💾 Database: {os.environ['DATABASE_PATH']}")
    print()
    print("Press Ctrl+C to stop the server")
    print("-" * 50)

    # Run the server with import string for reload to work
    uvicorn.run(
        "api.server:app",
        host=host,
        port=port,
        reload=True,  # Auto-reload on code changes
        log_level=log_level,
    )


if __name__ == "__main__":
    main()
