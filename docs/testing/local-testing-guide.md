# Local Testing Guide

This guide walks you through testing the Nostr Profiles API locally, including the new AI chat functionality.

## 🚀 Quick Start

### 1. Install Dependencies
```bash
# Install with Poetry (recommended)
poetry install

# Or with pip
pip install -r requirements.txt
```

### 2. Set Up Environment
Create a `.env` file in the project root:

```bash
# Required for chat functionality
OPENAI_API_KEY=sk-your-openai-api-key-here

# Optional - these have defaults for local testing
API_KEY=local_test_api_key
BEARER_TOKEN=local_test_bearer_token
ENVIRONMENT=development
HOST=127.0.0.1
PORT=8080
LOG_LEVEL=debug
```

### 3. Start the API Server
```bash
python scripts/run_api_service.py
```

You should see:
```
🚀 Starting local development server...
📊 API will be available at: http://127.0.0.1:8080
📖 API docs at: http://127.0.0.1:8080/docs
🔑 API Key for testing: local_test_api_key
```

## 🧪 Running Tests

### Option 1: Python Test Script (Recommended)
```bash
python tests/test_chat_local.py
```

This script tests:
- Server health check
- Streaming chat functionality
- Non-streaming chat functionality
- Multiple test queries

### Option 2: Bash/Curl Test Script
```bash
./tests/test_chat_local.sh
```

This script provides:
- curl-based testing
- Manual command examples
- Streaming response handling

### Option 3: Manual Testing

#### Test Basic Endpoints
```bash
# Health check
curl http://127.0.0.1:8080/health

# Database stats
curl -H "X-API-Key: local_test_api_key" \
     http://127.0.0.1:8080/api/stats

# Search profiles
curl -X POST http://127.0.0.1:8080/api/search \
  -H "X-API-Key: local_test_api_key" \
  -H "Content-Type: application/json" \
  -d '{"query": "coffee", "limit": 5}'
```

#### Test Chat Functionality

**Streaming Chat:**
```bash
curl -X POST http://127.0.0.1:8080/api/chat \
  -H "X-API-Key: local_test_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "Find me some coffee shops"}
    ],
    "stream": true
  }'
```

**Non-Streaming Chat:**
```bash
curl -X POST http://127.0.0.1:8080/api/chat \
  -H "X-API-Key: local_test_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "messages": [
      {"role": "user", "content": "What business types are available?"}
    ],
    "stream": false
  }'
```

## 🤖 Chat Testing Examples

Test these different types of queries to verify the AI assistant:

### Basic Queries
```json
{"messages": [{"role": "user", "content": "Find me restaurants"}]}
{"messages": [{"role": "user", "content": "Search for coffee shops"}]}
{"messages": [{"role": "user", "content": "Show me service businesses"}]}
```

### Business Type Queries
```json
{"messages": [{"role": "user", "content": "What business types are available?"}]}
{"messages": [{"role": "user", "content": "Find retail businesses"}]}
{"messages": [{"role": "user", "content": "Show me entertainment venues"}]}
```

### Statistics and Info
```json
{"messages": [{"role": "user", "content": "What's in the database?"}]}
{"messages": [{"role": "user", "content": "Show me database statistics"}]}
{"messages": [{"role": "user", "content": "How many businesses do you have?"}]}
```

### Conversational Context
```json
{
  "messages": [
    {"role": "user", "content": "Find me restaurants"},
    {"role": "assistant", "content": "I found several restaurants..."},
    {"role": "user", "content": "What about coffee shops?"}
  ]
}
```

## 🐛 Troubleshooting

### Common Issues

#### "OpenAI API key not configured"
**Problem:** Chat endpoint returns 500 error about missing OpenAI key.

**Solution:** 
1. Get an OpenAI API key from https://platform.openai.com/
2. Add it to your `.env` file: `OPENAI_API_KEY=sk-your-key-here`
3. Restart the server

#### "Rate limit exceeded"
**Problem:** Too many requests in testing.

**Solution:** 
- Wait a minute between test runs
- Reduce the number of test queries
- Check `RATE_LIMIT_REQUESTS` in your environment

#### "Profile search error"
**Problem:** Database is empty or corrupted.

**Solution:**
```bash
# Refresh database
curl -X POST http://127.0.0.1:8080/api/refresh \
  -H "X-API-Key: local_test_api_key"
```

#### "Connection refused"
**Problem:** Server not running.

**Solution:**
```bash
# Make sure server is running
python scripts/run_api_server.py
```

### Debug Mode

For more verbose logging, set:
```bash
export LOG_LEVEL=debug
python scripts/run_api_server.py
```

## 📊 Test Coverage

### Automated Tests
- Health check validation
- Authentication testing
- Streaming response handling
- Non-streaming response validation
- Error handling
- Multiple query types

### Manual Testing Areas
- Complex conversational flows
- Edge cases and error conditions
- Performance under load
- Different business types
- Long conversations

## 🔧 Advanced Testing

### Load Testing
```bash
# Simple load test with Apache Bench
ab -n 100 -c 10 -H "X-API-Key: local_test_api_key" \
   http://127.0.0.1:8080/health
```

### API Documentation
Visit http://127.0.0.1:8080/docs for interactive API documentation (available in development mode).

### Database Inspection
```bash
# Check database contents
python -c "
import sqlite3
conn = sqlite3.connect('local_test.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM resources')
print(f'Total records: {cursor.fetchone()[0]}')
conn.close()
"
```

## 🚀 Next Steps

After local testing:
1. Test with your API proxy (if using one)
2. Deploy to staging environment
3. Update your frontend to use the new chat endpoint
4. Monitor performance and usage patterns

## 📞 Support

If you encounter issues:
1. Check the server logs for error details
2. Verify your `.env` configuration
3. Test basic endpoints before chat functionality
4. Ensure you have a valid OpenAI API key with sufficient quota 
