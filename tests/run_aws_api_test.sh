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
API_URL="http://nostr-api-alb-792184217.us-east-1.elb.amazonaws.com"

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
  -d '{"query": "test", "limit": 5}' | jq .
echo -e "\n"

# 4. Search business profiles
echo "4. Testing business profile search..."
curl -X POST $API_URL/api/search_by_business_type \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"query": "retail", "business_type": "retail", "limit": 5}' | jq .
echo -e "\n"

# 5. Refresh database
echo "5. Testing database refresh..."
curl -X POST $API_URL/api/refresh -H "X-API-Key: $API_KEY" | jq .
echo -e "\n"

# 6. Get business types
echo "6. Testing business types endpoint..."
curl -X GET $API_URL/api/business_types -H "X-API-Key: $API_KEY" | jq .
echo -e "\n"

echo "All tests completed!"