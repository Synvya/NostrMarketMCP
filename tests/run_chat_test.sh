#!/bin/bash

# AWS API Testing Script
# Tests the deployed Nostr Profiles API

set -e

# Load environment variables from .env file
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
else
    echo "Error: .env file not found!"
    echo "Create a .env file with API_KEY=your_actual_api_key"
    exit 1
fi

# Check if API_KEY is set
if [ -z "$API_KEY" ]; then
    echo "Error: API_KEY not found in .env file!"
    exit 1
fi

# Set your API endpoint
API_URL="https://api.synvya.com"
PROXY_URL="https://proxy.synvya.com"

echo "Testing AWS API at: $API_URL"
echo "Using API Key: ${API_KEY:0:8}..." # Show only first 8 characters for security
echo ""

# 1. Health check (no auth)
echo "1. Testing health endpoint..."
curl -f $API_URL/health | jq .
echo -e "\n"

# 2. Test chat endpoint 
echo "8. Testing streaming response headers..."
echo "🔍 Checking if Content-Type fix is deployed..."
curl -I -X POST $API_URL/api/chat \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"find coffee in snoqualmie, wa"}],"stream":false}' | jq
echo -e "\n"

# 3. Traces
curl -s -H "X-API-Key: $API_KEY" "$API_URL/api/debug/last_tool_loop" | jq
echo -e "\n\n"

echo "All tests completed!"