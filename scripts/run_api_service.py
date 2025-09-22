#!/usr/bin/env python3
"""
Launch the API service locally for testing.
"""

import logging
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so 'src.*' imports resolve
sys.path.insert(0, str(Path(__file__).parent.parent))

import uvicorn
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Start the API service locally."""
    # Load environment variables
    project_root = Path(__file__).parent.parent
    load_dotenv(project_root / ".env")

    # Set test environment
    os.environ["ENVIRONMENT"] = "test"

    # Ensure we're using the right Python environment
    # The script should be run with the activated virtual environment

    # API service configuration
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("API_SERVICE_PORT", "8080"))

    # Configure database service URL for local testing
    os.environ["DATABASE_SERVICE_URL"] = "http://localhost:8082"

    logger.info(f"Starting API Service on http://{host}:{port}")
    logger.info("Database service URL: http://localhost:8082")
    logger.info("Environment: test")

    # Run the API service with test-friendly configuration
    uvicorn_config = {
        "app": "src.api.server:app",
        "host": host,
        "port": port,
        "log_level": "info",
        "access_log": True,
        "reload": False,
    }

    # Add test-specific optimizations
    if os.getenv("ENVIRONMENT") == "test":
        uvicorn_config.update(
            {
                "log_level": "warning",  # Reduce log noise in tests
                "access_log": False,  # Disable access logs for faster testing
                "loop": "asyncio",  # Use asyncio loop for better compatibility
                "http": "h11",  # Use h11 for simpler HTTP handling
            }
        )
        logger.info("Using test-optimized uvicorn configuration")

    uvicorn.run(**uvicorn_config)


if __name__ == "__main__":
    main()
