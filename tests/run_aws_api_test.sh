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
# API_URL="http://nostr-api-alb-792184217.us-east-1.elb.amazonaws.com"
API_URL="https://api.synvya.com"

echo "Testing AWS API at: $API_URL"
echo "Using API Key: ${API_KEY:0:8}..." # Show only first 8 characters for security
echo ""

# 1. Health check (no auth)
echo "1. Testing health endpoint..."
curl -f $API_URL/health | jq .
echo -e "\n"

# 2. Get database stats
echo "2. Testing database stats..."
curl -X GET $API_URL/api/stats -H "X-API-Key: $API_KEY" | jq .
echo -e "\n"

# 3. Search for profiles
echo "3. Testing profile search..."
curl -X POST $API_URL/api/search \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "bookkeeping, bookkeeper", "limit": 5}' | jq .
echo -e "\n"

# 4. Search business profiles
echo "4. Testing business profile search..."
curl -X POST $API_URL/api/search_by_business_type \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "software", "business_type": "retail", "limit": 5}' | jq .
echo -e "\n"

# 5. Refresh database
echo "5. Testing database refresh..."
curl -X POST $API_URL/api/refresh -H "X-API-Key: $API_KEY" | jq .
echo -e "\n"

# 6. Get business types
echo "6. Testing business types endpoint..."
curl -X GET $API_URL/api/business_types -H "X-API-Key: $API_KEY" | jq .
echo -e "\n"

# 7. Get specific profile
echo "7. Testing specific profile..." 
curl -X GET $API_URL/api/profile/38267cf358b0b2fe41dfbbc491f288b8df1ed0291dce5862e4a209df96078ab8 -H "X-API-Key: $API_KEY" | jq .
echo -e "\n"

# 8. Test chat endpoint (non-streaming)
echo "8. Testing chat endpoint (non-streaming)..."
curl -X POST $API_URL/api/chat \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What business types are available?"}
    ],
    "stream": false,
    "max_tokens": 200
  }' | jq .
echo -e "\n"

# 9. Test chat endpoint (streaming) - Enhanced
echo "9. Testing chat endpoint (streaming)..."
echo "💬 Asking: 'Find me some coffee shops'"
echo "🔄 Testing streaming response (should show data chunks)..."

# Test streaming with better error handling and timeout
timeout 30s curl -X POST $API_URL/api/chat \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Find me some coffee shops"}
    ],
    "stream": true,
    "max_tokens": 150
  }' -N --no-buffer -w "\nHTTP Status: %{http_code}\nTotal Time: %{time_total}s\n" || {
    echo "❌ Streaming request failed or timed out"
    echo "This might indicate the HTTP/2 framing issue is still present"
}
echo -e "\n"

# 10. Additional streaming test with simple query
echo "10. Testing streaming with simple query..."
echo "💬 Asking: 'Hello'"
timeout 15s curl -X POST $API_URL/api/chat \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Hello"}
    ],
    "stream": true,
    "max_tokens": 50
  }' -N --no-buffer || {
    echo "❌ Simple streaming test failed"
}
echo -e "\n\n"

echo "All tests completed!"