"""Pytest configuration for NostrMarketMCP tests."""

import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio

# Set environment variables for testing
os.environ.setdefault("MCP_BEARER", "test_token")


# Skip integration tests by default
def pytest_addoption(parser):
    """Add option to run integration tests."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests",
    )


def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line("markers", "integration: mark test as integration test")


def pytest_collection_modifyitems(config, items):
    """Skip integration tests if --run-integration is not specified."""
    if config.getoption("--run-integration"):
        return

    skip_integration = pytest.mark.skip(reason="Need --run-integration option to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
