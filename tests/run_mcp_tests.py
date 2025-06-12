#!/usr/bin/env python3
"""
Test runner for Nostr Profiles MCP Server.

Runs all MCP server tests with proper environment setup.
"""

import os
import subprocess
import sys
from pathlib import Path


def run_mcp_tests():
    """Run the MCP server tests."""
    print("🚀 Running Nostr Profiles MCP Server Tests")
    print("=" * 50)

    # Set environment variables for testing
    os.environ["ENVIRONMENT"] = "test"

    # Run the tests
    print("🧪 Running MCP server tests...")
    try:
        # Run pytest with verbose output
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_mcp_server.py",
                "-v",  # Verbose output
                "--tb=short",  # Short traceback format
                "--color=yes",  # Colored output
                "-x",  # Stop on first failure
            ],
            check=True,
        )

        print("\n🎉 All MCP server tests passed!")
        return 0

    except subprocess.CalledProcessError as e:
        print(f"\n❌ MCP server tests failed with exit code: {e.returncode}")
        return e.returncode
    except Exception as e:
        print(f"\n❌ Error running MCP server tests: {e}")
        return 1


def run_specific_mcp_test(test_name):
    """Run a specific MCP test."""
    print(f"🧪 Running specific MCP test: {test_name}")
    print("=" * 50)

    os.environ["ENVIRONMENT"] = "test"

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                f"tests/test_mcp_server.py::{test_name}",
                "-v",
                "--tb=short",
                "--color=yes",
            ],
            check=True,
        )

        print(f"\n✅ MCP test {test_name} passed!")
        return 0

    except subprocess.CalledProcessError as e:
        print(f"\n❌ MCP test {test_name} failed!")
        return e.returncode


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        # Run specific test
        test_name = sys.argv[1]
        return run_specific_mcp_test(test_name)
    else:
        # Run all MCP tests
        return run_mcp_tests()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
