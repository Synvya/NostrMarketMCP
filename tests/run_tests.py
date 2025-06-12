#!/usr/bin/env python3
"""
Test runner for Nostr Profiles API.

Runs all API endpoint tests and provides detailed output.
"""

import subprocess
import sys
import time
from pathlib import Path

import httpx


def check_server_running():
    """Check if the API server is running."""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get("http://127.0.0.1:8080/health")
            return response.status_code == 200
    except:
        return False


def run_tests():
    """Run the API endpoint tests."""
    print("🚀 Running Nostr Profiles API Tests")
    print("=" * 50)

    # Check if server is running
    print("Checking if server is running...")
    if not check_server_running():
        print("❌ ERROR: API server is not running!")
        print("\n📝 To start the server, run:")
        print("   python run_local.py")
        return 1

    print("✅ Server is running!")
    print()

    # Run the tests
    print("🧪 Running tests...")
    try:
        # Run pytest with verbose output
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_api_endpoints.py",
                "-v",  # Verbose output
                "--tb=short",  # Short traceback format
                "--color=yes",  # Colored output
                "-x",  # Stop on first failure
            ],
            check=True,
        )

        print("\n🎉 All tests passed!")
        return 0

    except subprocess.CalledProcessError as e:
        print(f"\n❌ Tests failed with exit code: {e.returncode}")
        return e.returncode
    except Exception as e:
        print(f"\n❌ Error running tests: {e}")
        return 1


def run_specific_test(test_name):
    """Run a specific test."""
    print(f"🧪 Running specific test: {test_name}")
    print("=" * 50)

    if not check_server_running():
        print("❌ ERROR: API server is not running!")
        return 1

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                f"tests/test_api_endpoints.py::{test_name}",
                "-v",
                "--tb=short",
                "--color=yes",
            ],
            check=True,
        )

        print(f"\n✅ Test {test_name} passed!")
        return 0

    except subprocess.CalledProcessError as e:
        print(f"\n❌ Test {test_name} failed!")
        return e.returncode


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        # Run specific test
        test_name = sys.argv[1]
        return run_specific_test(test_name)
    else:
        # Run all tests
        return run_tests()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
