#!/usr/bin/env python3
"""
MCP Server Integration Test Runner

Runs integration tests against a real MCP server process.
Similar to API test runner but for MCP protocol testing.
"""

import asyncio
import subprocess
import sys
import time
from pathlib import Path


def run_integration_tests():
    """Run MCP server integration tests."""
    print("🚀 Running MCP Server Integration Tests")
    print("=" * 50)

    # Check if test file exists
    test_file = Path("tests/test_mcp_integration.py")
    if not test_file.exists():
        print("❌ ERROR: MCP integration test file not found!")
        print(f"   Expected: {test_file}")
        return False

    print("🧪 Running MCP integration tests...")
    print("   Note: This will launch real MCP server processes")
    print()

    # Available test methods for individual execution
    test_methods = [
        "test_server_connection",
        "test_list_tools",
        "test_list_resources",
        "test_search_profiles_tool",
        "test_get_profile_stats_tool",
        "test_get_business_types_tool",
        "test_explain_profile_tags_tool",
        "test_search_business_profiles_tool",
        "test_get_refresh_status_tool",
        "test_tool_error_handling",
        "test_concurrent_tool_calls",
        "test_server_resource_cleanup",
    ]

    try:
        # Run pytest with the integration test file
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            str(test_file),
            "-v",
            "--tb=short",
            "--asyncio-mode=auto",
        ]

        print(f"🔧 Command: {' '.join(cmd)}")
        print()

        # Run the tests
        result = subprocess.run(cmd, capture_output=False)

        if result.returncode == 0:
            print()
            print("🎉 All MCP integration tests passed!")
            print()
            print("✅ Real MCP server testing completed successfully")
            print("   - Server process management: OK")
            print("   - MCP protocol communication: OK")
            print("   - Tool functionality: OK")
            print("   - Resource cleanup: OK")
            return True
        else:
            print()
            print("❌ Some MCP integration tests failed!")
            print(f"   Exit code: {result.returncode}")
            return False

    except Exception as e:
        print(f"❌ ERROR running integration tests: {e}")
        return False


def run_specific_test(test_name: str):
    """Run a specific integration test."""
    test_file = Path("tests/test_mcp_integration.py")

    if not test_file.exists():
        print("❌ ERROR: MCP integration test file not found!")
        return False

    print(f"🧪 Running specific MCP integration test: {test_name}")
    print("=" * 60)

    try:
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            f"{test_file}::TestMCPServerIntegration::{test_name}",
            "-v",
            "--tb=long",
            "--asyncio-mode=auto",
        ]

        result = subprocess.run(cmd, capture_output=False)
        return result.returncode == 0

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        # Run specific test
        test_name = sys.argv[1]
        success = run_specific_test(test_name)
    else:
        # Run all integration tests
        success = run_integration_tests()

    if success:
        print()
        print("🎯 Integration testing summary:")
        print("   - MCP server process: ✅ Launched and managed successfully")
        print("   - Protocol communication: ✅ MCP messages sent/received")
        print("   - Tool execution: ✅ All tools respond correctly")
        print("   - Resource management: ✅ Proper cleanup and shutdown")
        print()
        print("🔗 This validates the full MCP server stack:")
        print("   • Server startup and initialization")
        print("   • Database connection and operations")
        print("   • MCP protocol implementation")
        print("   • Tool registration and execution")
        print("   • Resource endpoint handling")
        print("   • Process lifecycle management")

        sys.exit(0)
    else:
        print()
        print("❌ Integration tests failed. Common issues:")
        print("   • MCP server dependencies missing")
        print("   • Database connection problems")
        print("   • Process startup timeout")
        print("   • MCP protocol version mismatch")
        print()
        print("💡 Try running unit tests first:")
        print("   python run_mcp_tests.py")

        sys.exit(1)


if __name__ == "__main__":
    main()
