# OpenAI Custom GPT Integration

This guide shows how to integrate your Nostr Profiles data with OpenAI Custom GPTs using Actions.

## Quick Start

### 1. Start the REST API Server
```bash
# Run the OpenAI-compatible REST API server
python openai_api_server.py
```
The server will start on `http://localhost:8080` with:
- Interactive docs at `/docs`
- OpenAPI schema at `/openapi.json`

### 2. Create OpenAI Custom GPT

1. Go to [OpenAI Custom GPTs](https://chat.openai.com/gpts/editor)
2. Click "Create a GPT"
3. Configure the GPT:
   - **Name**: "Nostr Business Profiles Search"
   - **Description**: "Search and analyze Nostr business profiles with L/business.type tags"
   - **Instructions**: See below

### 3. Add Actions

1. In the GPT editor, go to "Actions"
2. Click "Create new action"
3. **Option A**: Import schema file
   - Upload `openai_actions_schema.yaml`
   
   **Option B**: Copy from running server
   - Copy the schema from `http://localhost:8080/openapi.json`

### 4. Configure Server URL

Update the schema to point to your server:
```yaml
servers:
  - url: http://localhost:8080  # For local testing
  # - url: https://your-domain.com  # For production
```

## GPT Instructions Template

```
You are a Nostr Business Profiles Search assistant. You help users find and analyze Nostr profiles, especially business profiles that have "L" "business.type" tags.

## Your Capabilities:
- Search all Nostr profiles by content (name, about, nip05, etc.)
- Search specifically for business profiles with type filtering
- Get detailed profile information by public key
- Provide database statistics
- Refresh the database with new profiles from Nostr relays

## Business Types Available:
- retail
- restaurant  
- services
- business
- entertainment
- other

## When to use each function:
- Use `searchProfiles` for general profile searches
- Use `searchBusinessProfiles` for business-specific searches with filtering
- Use `getProfile` when you have a specific public key
- Use `getStats` to show database overview
- Use `refreshDatabase` to get the latest data from Nostr relays

## Response Format:
- Always provide helpful summaries of search results
- Include relevant profile details like name, about, website, nip05
- For business profiles, highlight the business type and relevant tags
- Suggest related searches when appropriate
```

## Available Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/search_profiles` | POST | Search all profiles by content |
| `/api/search_business_profiles` | POST | Search business profiles with filtering |
| `/api/profile/{pubkey}` | GET | Get specific profile by public key |
| `/api/stats` | GET | Get database statistics |
| `/api/business_types` | GET | Get available business type filters |
| `/api/refresh` | POST | Refresh database from Nostr relays |

## Example Usage

### Search Business Profiles
```json
POST /api/search_business_profiles
{
  "query": "coffee",
  "business_type": "restaurant",
  "limit": 5
}
```

### Search All Profiles
```json
POST /api/search_profiles
{
  "query": "bitcoin developer",
  "limit": 10
}
```

## Testing the API

### Using curl
```bash
# Test basic functionality
curl http://localhost:8080/health

# Search profiles
curl -X POST http://localhost:8080/api/search_profiles \
  -H "Content-Type: application/json" \
  -d '{"query": "test", "limit": 5}'

# Get stats
curl http://localhost:8080/api/stats
```

### Using the interactive docs
Visit `http://localhost:8080/docs` to test all endpoints interactively.

## Deployment Notes

### For Production:
1. **Update server URL** in the OpenAPI schema
2. **Add authentication** if needed
3. **Configure CORS** appropriately
4. **Use a process manager** like PM2 or systemd
5. **Set up reverse proxy** with nginx/Apache
6. **Use HTTPS** for secure connections

### Example production command:
```bash
# Install dependencies
pip install uvicorn[standard]

# Run with uvicorn directly
uvicorn openai_api_server:app --host 0.0.0.0 --port 8080 --workers 4
```

## Architecture

```
OpenAI Custom GPT
       ↓ (Actions/HTTP)
REST API Server (FastAPI)
       ↓ (Function calls)
MCP Server Functions
       ↓ (Database calls)
SQLite Database
       ↑ (Refresh data)
Nostr Relays
```

## Benefits

✅ **Dual Integration**: Works with both Claude/MCP and OpenAI/GPT  
✅ **Structured Data**: Proper Pydantic models and validation  
✅ **Auto Documentation**: Interactive OpenAPI docs  
✅ **Type Safety**: Full type hints and validation  
✅ **Real-time Data**: Database refresh from Nostr relays  
✅ **Business Focus**: Specialized business profile search

Your Nostr profiles data is now accessible to both MCP clients (Claude) and OpenAI Custom GPTs! 🚀 