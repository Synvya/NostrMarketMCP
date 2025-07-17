#!/bin/bash

# Local Chat API Testing Script (Bash/Curl Version)
# Tests the new chat functionality with OpenAI integration

set -e

# Configuration
BASE_URL="http://127.0.0.1:8080"

# Load environment variables from .env file if it exists
if [ -f ".env" ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Use environment variables or defaults
API_KEY=${API_KEY:-"local_test_api_key"}
OPENAI_API_KEY=${OPENAI_API_KEY:-""}

echo "🧪 Chat API Local Testing (Curl Version)"
echo "========================================"
echo ""
echo "🔧 Configuration:"
echo "   Base URL: $BASE_URL"
echo "   API Key: ${API_KEY:0:8}..."
echo "   OpenAI Key: $([ -n "$OPENAI_API_KEY" ] && echo "Set" || echo "Not set")"
echo ""

# Check if OpenAI key is configured
if [ -z "$OPENAI_API_KEY" ]; then
    echo "⚠️  WARNING: OPENAI_API_KEY not found!"
    echo "   Please set OPENAI_API_KEY in your .env file or environment variables"
    echo "   Chat functionality will not work without it."
    echo ""
fi

# 1. Health check
echo "1. Testing health endpoint..."
if curl -f -s "$BASE_URL/health" | jq . > /dev/null 2>&1; then
    echo "✅ Server is healthy"
else
    echo "❌ Server is not running. Please start it with:"
    echo "   python scripts/run_api_server.py"
    exit 1
fi
echo ""

# 2. Test non-streaming chat
echo "2. Testing non-streaming chat..."
echo "💬 Asking: 'What business types are available?'"

CHAT_RESPONSE=$(curl -s -X POST "$BASE_URL/api/chat" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "messages": [
      {"role": "user", "content": "What business types are available?"}
    ],
    "stream": false,
    "max_tokens": 300
  }')

if echo "$CHAT_RESPONSE" | jq -e '.success' > /dev/null 2>&1; then
    echo "✅ Non-streaming chat successful"
    echo "📝 Response preview:"
    echo "$CHAT_RESPONSE" | jq -r '.message.content' | head -c 200
    echo "..."
else
    echo "❌ Non-streaming chat failed"
    echo "Error: $CHAT_RESPONSE"
fi
echo ""

# 3. Test streaming chat
echo "3. Testing streaming chat..."
echo "💬 Asking: 'Find me some coffee shops'"
echo "📡 Streaming response:"

# Create a temporary file for the curl output
TEMP_FILE=$(mktemp)

# Start streaming chat request
curl -s -X POST "$BASE_URL/api/chat" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "messages": [
      {"role": "user", "content": "Find me some coffee shops"}
    ],
    "stream": true,
    "max_tokens": 500
  }' > "$TEMP_FILE" 2>&1 &

CURL_PID=$!

# Wait a moment and then check if curl is still running
sleep 3

if kill -0 $CURL_PID 2>/dev/null; then
    echo "🔄 Chat is streaming... (waiting for completion)"
    wait $CURL_PID
else
    echo "⚡ Chat completed quickly"
fi

# Check the output
if [ -s "$TEMP_FILE" ]; then
    echo ""
    echo "📄 Raw streaming output (first 500 chars):"
    head -c 500 "$TEMP_FILE"
    echo ""
    echo "✅ Streaming chat completed"
else
    echo "❌ No streaming output received"
fi

# Cleanup
rm -f "$TEMP_FILE"
echo ""

# 4. Test business search chat
echo "4. Testing business search via chat..."
echo "💬 Asking: 'Search for restaurants'"

BUSINESS_RESPONSE=$(curl -s -X POST "$BASE_URL/api/chat" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $API_KEY" \
  -d '{
    "messages": [
      {"role": "user", "content": "Search for restaurants"}
    ],
    "stream": false,
    "max_tokens": 400
  }')

if echo "$BUSINESS_RESPONSE" | jq -e '.success' > /dev/null 2>&1; then
    echo "✅ Business search chat successful"
    echo "📝 Response preview:"
    echo "$BUSINESS_RESPONSE" | jq -r '.message.content' | head -c 200
    echo "..."
else
    echo "❌ Business search chat failed"
    echo "Error: $BUSINESS_RESPONSE"
fi
echo ""

echo "🎯 Testing completed!"
echo ""
echo "💡 Tips for manual testing:"
echo "   • Use curl with streaming to see real-time responses"
echo "   • Test different queries: restaurants, coffee shops, developers, etc."
echo "   • Try asking for statistics: 'Show me database stats'"
echo "   • Test business type queries: 'Find service businesses'"
echo ""
echo "🔗 Example streaming command:"
echo "curl -X POST $BASE_URL/api/chat \\"
echo "  -H 'Content-Type: application/json' \\"
echo "  -H 'X-API-Key: $API_KEY' \\"
echo "  -d '{\"messages\":[{\"role\":\"user\",\"content\":\"Find coffee shops\"}],\"stream\":true}'" 