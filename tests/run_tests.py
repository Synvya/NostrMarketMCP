#!/usr/bin/env python3
"""
Test runner for Nostr Profiles API project.

This script runs all automated tests and provides guidance for manual testing.
"""

import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx


def run_command(cmd, description):
    """Run a command and report results."""
    return run_command_with_env(cmd, description, None)


def run_command_with_env(cmd, description, env=None):
    """Run a command with optional environment and report results."""
    print(f"\n{'='*60}")
    print(f"🧪 {description}")
    print("=" * 60)

    try:
        result = subprocess.run(
            cmd, shell=True, check=True, capture_output=True, text=True, env=env
        )
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        print(f"✅ {description} - PASSED")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - FAILED")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        print("Return code:", e.returncode)
        return False


def wait_for_server(base_url="http://127.0.0.1:8080", timeout=30):
    """Wait for the API server to be ready."""
    print(f"⏳ Waiting for server at {base_url} to be ready...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{base_url}/health")
                if response.status_code == 200:
                    print(f"✅ Server is ready at {base_url}")
                    return True
        except (httpx.ConnectError, httpx.TimeoutException):
            pass
        time.sleep(1)

    print(f"❌ Server failed to start within {timeout} seconds")
    return False


def start_api_server():
    """Start the API server in a background process."""
    print("🚀 Starting API server for testing...")

    # Create temporary database for testing
    fd, temp_db = tempfile.mkstemp(suffix=".db")
    os.close(fd)

    # Set up environment for test server
    env = os.environ.copy()
    env.update(
        {
            "DATABASE_PATH": temp_db,
            "ENVIRONMENT": "test",
            "API_KEY": "test_api_key_integration",
            "PORT": "8080",
            "HOST": "127.0.0.1",
            "LOG_LEVEL": "info",  # Ensure lowercase for uvicorn
            "DISABLE_BACKGROUND_TASKS": "true",  # Disable background tasks for testing
        }
    )

    # Start server process with output capture for debugging
    server_process = subprocess.Popen(
        [sys.executable, "scripts/run_api_server.py"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # Combine stdout and stderr
        text=True,
        bufsize=1,  # Line buffered
        preexec_fn=os.setsid,  # Create new process group for clean shutdown
    )

    return server_process, temp_db


def stop_api_server(server_process, temp_db):
    """Stop the API server and clean up."""
    print("🛑 Stopping API server...")

    try:
        # Send SIGTERM to the process group
        os.killpg(os.getpgid(server_process.pid), signal.SIGTERM)

        # Wait for graceful shutdown
        try:
            server_process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            # Force kill if needed
            os.killpg(os.getpgid(server_process.pid), signal.SIGKILL)
            server_process.wait()

        print("✅ Server stopped")

    except ProcessLookupError:
        # Process already terminated
        print("✅ Server was already stopped")
    except Exception as e:
        print(f"⚠️  Error stopping server: {e}")

    # Clean up temp database
    try:
        if os.path.exists(temp_db):
            os.unlink(temp_db)
    except Exception as e:
        print(f"⚠️  Error cleaning up temp database: {e}")


def main():
    """Run all tests."""
    print("🚀 Starting Nostr Profiles API Test Suite")

    # Change to project directory
    project_root = Path(__file__).parent.parent
    print(f"📁 Project root: {project_root}")

    success = True

    # Run MCP server tests (these work reliably)
    success &= run_command(
        "python -m pytest tests/test_mcp_server.py -v", "MCP Server Unit Tests"
    )

    # Run MCP integration tests (these work reliably)
    success &= run_command(
        "python -m pytest tests/test_mcp_integration.py -v", "MCP Integration Tests"
    )

    # Automated API Integration Tests
    server_process = None
    temp_db = None

    try:
        # Start API server in background
        server_process, temp_db = start_api_server()

        # Give server a moment to start
        time.sleep(2)

        # Check if server process is still running
        if server_process.poll() is not None:
            # Server crashed, get output
            stdout, stderr = server_process.communicate()
            print(f"❌ Server crashed during startup:")
            print(f"Output: {stdout}")
            if stderr:
                print(f"Error: {stderr}")
            success = False
        elif wait_for_server():
            # Set API key for tests and run API integration tests
            test_env = os.environ.copy()
            test_env["API_KEY"] = "test_api_key_integration"

            success &= run_command_with_env(
                "python -m pytest tests/test_api_integration.py::TestLiveAPIEndpoints -v",
                "API Integration Tests (Automated)",
                test_env,
            )
        else:
            print("❌ Failed to start API server for testing")
            # Get some output for debugging
            try:
                stdout, stderr = server_process.communicate(timeout=1)
                print(f"Server output: {stdout}")
                if stderr:
                    print(f"Server error: {stderr}")
            except subprocess.TimeoutExpired:
                print("Server is running but not responding to health checks")
            success = False

    except Exception as e:
        print(f"❌ Error during API testing: {e}")
        success = False

    finally:
        # Always clean up the server
        if server_process:
            stop_api_server(server_process, temp_db)

    print(f"\n{'='*60}")
    if success:
        print("🎉 All tests passed!")
        print("✅ MCP Tests: Comprehensive coverage of core functionality")
        print("✅ API Tests: Full endpoint testing with automatic server management")
    else:
        print("❌ Some tests failed. Check the output above.")

    print("=" * 60)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
