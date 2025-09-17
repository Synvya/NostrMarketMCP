#!/usr/bin/env python3
"""
Launch the database service locally for testing.
"""

import logging
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path so 'src.*' imports resolve
sys.path.insert(0, str(Path(__file__).parent.parent))

import socket
import uvicorn
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Start the database service locally."""
    # Load environment variables
    project_root = Path(__file__).parent.parent
    load_dotenv(project_root / ".env")

    # Set test environment
    os.environ["ENVIRONMENT"] = "test"

    # Use local database path for testing
    test_db_path = project_root / "test_database.db"
    os.environ["DATABASE_PATH"] = str(test_db_path)

    # Database service configuration
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("DATABASE_SERVICE_PORT", "8082"))

    logger.info(f"Starting Database Service on http://{host}:{port}")
    logger.info(f"Database path: {test_db_path}")
    logger.info("Environment: test")

    # Skip if port already in use (service likely running)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        try:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                logger.info(
                    f"Database service already running on port {port}; skipping start"
                )
                return
        except Exception:
            pass

    # Run the database service
    uvicorn.run(
        "src.database_service.server:app",
        host=host,
        port=port,
        log_level="info",
        access_log=True,
        reload=False,
    )


if __name__ == "__main__":
    main()
