#!/usr/bin/env python3
"""
Local Chat API Testing Script

Tests the new chat functionality with OpenAI integration.
This script helps you test the chat endpoint locally.
"""

import json
import os
import time
from typing import Any, Dict

import requests


def load_env_from_file(env_file: str = ".env") -> Dict[str, str]:
    """Load environment variables from .env file."""
    env_vars = {}
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key] = value
    return env_vars


def test_health_check(base_url: str) -> bool:
    """Test if the API server is running."""
    try:
        response = requests.get(f"{base_url}/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Server is healthy: {data.get('service', 'Unknown')}")
            print(f"   Environment: {data.get('environment', 'Unknown')}")
            print(f"   Auth configured: {data.get('auth_configured', False)}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot connect to server: {e}")
        return False


def test_chat_streaming(base_url: str, api_key: str, message: str) -> bool:
    """Test streaming chat functionality."""
    print(f"\n🤖 Testing streaming chat with message: '{message}'")

    chat_data = {
        "messages": [{"role": "user", "content": message}],
        "stream": True,
        "max_tokens": 500,
        "temperature": 0.7,
    }

    try:
        response = requests.post(
            f"{base_url}/api/chat",
            headers={"Content-Type": "application/json", "X-API-Key": api_key},
            json=chat_data,
            stream=True,
            timeout=30,
        )

        if response.status_code != 200:
            print(f"❌ Chat request failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

        print("📡 Streaming response:")
        full_response = ""

        for line in response.iter_lines():
            if line:
                line_str = line.decode("utf-8")
                if line_str.startswith("data: "):
                    try:
                        data = json.loads(line_str[6:])
                        if "content" in data:
                            content = data["content"]
                            print(content, end="", flush=True)
                            full_response += content
                        elif "done" in data:
                            print(f"\n✅ Chat completed successfully")
                            return True
                        elif "error" in data:
                            print(f"\n❌ Chat error: {data['error']}")
                            return False
                    except json.JSONDecodeError:
                        continue

        return True

    except Exception as e:
        print(f"❌ Chat test failed: {e}")
        return False


def test_chat_non_streaming(base_url: str, api_key: str, message: str) -> bool:
    """Test non-streaming chat functionality."""
    print(f"\n🤖 Testing non-streaming chat with message: '{message}'")

    chat_data = {
        "messages": [{"role": "user", "content": message}],
        "stream": False,
        "max_tokens": 300,
        "temperature": 0.7,
    }

    try:
        response = requests.post(
            f"{base_url}/api/chat",
            headers={"Content-Type": "application/json", "X-API-Key": api_key},
            json=chat_data,
            timeout=30,
        )

        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                message_content = data.get("message", {}).get("content", "")
                print(f"📝 Response: {message_content[:200]}...")
                print("✅ Non-streaming chat completed successfully")
                return True
            else:
                print(f"❌ Chat failed: {data}")
                return False
        else:
            print(f"❌ Chat request failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Chat test failed: {e}")
        return False


def main():
    """Main testing function."""
    print("🧪 Chat API Local Testing")
    print("=" * 40)

    # Configuration
    base_url = "http://127.0.0.1:8080"

    # Load environment variables
    env_vars = load_env_from_file(".env")
    api_key = env_vars.get("API_KEY") or os.getenv("API_KEY", "local_test_api_key")
    openai_key = env_vars.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")

    print(f"🔧 Configuration:")
    print(f"   Base URL: {base_url}")
    print(f"   API Key: {api_key[:8]}..." if api_key else "   API Key: Not set")
    print(f"   OpenAI Key: {'Set' if openai_key else 'Not set'}")
    print()

    # Check if OpenAI key is configured
    if not openai_key:
        print("⚠️  WARNING: OPENAI_API_KEY not found!")
        print("   Please set OPENAI_API_KEY in your .env file or environment variables")
        print("   Chat functionality will not work without it.")
        print()

    # 1. Health check
    if not test_health_check(base_url):
        print("\n❌ Server is not running. Please start it with:")
        print("   python scripts/run_api_server.py")
        return

    # 2. Test chat functionality
    test_messages = [
        "Find me some coffee shops",
        "What business types are available?",
        "Search for restaurants in Seattle",
        "Show me database statistics",
    ]

    success_count = 0
    total_tests = len(test_messages) * 2  # Both streaming and non-streaming

    for message in test_messages:
        # Test streaming
        if test_chat_streaming(base_url, api_key, message):
            success_count += 1

        time.sleep(1)  # Brief pause between tests

        # Test non-streaming
        if test_chat_non_streaming(base_url, api_key, message):
            success_count += 1

        time.sleep(1)  # Brief pause between tests

    # Summary
    print(f"\n📊 Test Summary:")
    print(f"   Passed: {success_count}/{total_tests}")
    print(f"   Success rate: {(success_count/total_tests)*100:.1f}%")

    if success_count == total_tests:
        print("🎉 All tests passed!")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")


if __name__ == "__main__":
    main()
