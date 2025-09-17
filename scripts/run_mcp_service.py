#!/usr/bin/env python3
"""
Launch the MCP service locally for testing.
"""

import logging
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import socket
import uvicorn
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Start the MCP service locally."""
    # Load environment variables
    project_root = Path(__file__).parent.parent
    load_dotenv(project_root / ".env")

    # Set test environment
    os.environ["ENVIRONMENT"] = "test"

    # MCP service configuration
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("MCP_SERVICE_PORT", "8081"))

    # Configure database service URL for local testing
    os.environ["DATABASE_SERVICE_URL"] = "http://localhost:8082"

    logger.info(f"Starting MCP Service on http://{host}:{port}")
    logger.info("Database service URL: http://localhost:8082")
    logger.info("Environment: test")

    # Skip if port already in use (service likely running)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        try:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                logger.info(
                    f"MCP service already running on port {port}; skipping start"
                )
                return
        except Exception:
            pass

    # Run the MCP service
    uvicorn.run(
        "src.mcp.server:app",
        host=host,
        port=port,
        log_level="info",
        access_log=True,
        reload=False,
    )


if __name__ == "__main__":
    main()
