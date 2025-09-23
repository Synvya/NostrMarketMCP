# NostrProfileMCP

Bridge that turns Nostr profile events into an **MCP over HTTP server** for AI agents with automatic business profile discovery.

## Overview

NostrMarketMCP ingests Nostr profile events (kind 0) and marketplace stalls (kind 30017), persists them in a SQLite database, and exposes them as resources and tools via an **HTTP MCP-compatible server using JSON-RPC**. This allows AI agents like Claude to interact with Nostr profile information, marketplace stalls, search profiles and stalls, and analyze user data through the **Model Context Protocol over HTTP**.

**🚀 NEW: MCP over HTTP Implementation**
- **Streamable HTTP**: Single HTTP endpoint accepting JSON-RPC POSTs with SSE streaming responses
- **Claude Compatible**: Full MCP protocol compliance for Claude and other MCP clients
- **JSON-RPC Protocol**: Proper MCP over HTTP transport instead of stdio
- **Real-time Streaming**: Server-Sent Events (SSE) support for live data streaming

**NEW:** The server now automatically refreshes its database with business profiles from Nostr relays at startup and every 5 minutes, specifically targeting profiles with "L" "business.type" tags.

## Architecture

For a concise overview of how the three services (Database, API, MCP) fit together and deploy to AWS, see:
- `docs/Architecture.md`

## Features

- **MCP over HTTP**: JSON-RPC protocol with optional Server-Sent Events streaming ✨ **NEW**
- **Claude Integration**: Full compatibility with Claude and other MCP clients ✨ **NEW**
- **Automatic Business Profile Discovery**: Searches Nostr relays for kind:0 profiles with "L" "business.type" tags
- **Scheduled Refresh**: Automatically refreshes the database every 5 minutes with new business profiles
- **Manual Refresh**: Ability to manually trigger profile refresh from Nostr relays
- Monitors Nostr relays for profile events (kind 0) and marketplace stalls (kind 30017)
- Persists profile and stall events in a local SQLite database
- Exposes profile and stall data as MCP-compatible resources and tools
- Provides tools for searching profiles by name, about, nip05, and other metadata
- Provides tools for searching marketplace stalls by name, description, and merchant
- **Business Profile Search**: Specialized search for business profiles with filtering by business type
- **Marketplace Stalls**: Full support for Nostr marketplace stalls with search and statistics
- Profile and stall statistics and analytics
- Optional targeted monitoring of specific pubkeys or global profile monitoring

## Installation

```bash
# Install with Poetry
poetry install

# Or with pip
pip install .
```

## Quick Start (Reorganized Codebase)

**NEW**: The codebase has been reorganized for better maintainability:

```
src/
├── api/           # HTTP API server for web/OpenAI integration
├── mcp/           # MCP over HTTP server for Claude/MCP clients ✨ UPDATED
└── core/          # Database and shared components
tests/             # All tests and test runners
```

### Run HTTP API Server (for web/OpenAI integration)
```bash
python scripts/run_api_server.py
# Available at http://127.0.0.1:8080
# API Key: local_test_api_key
```

### API Chat Authentication (server‑side)

- The API's `/api/chat` endpoint uses a server‑side OpenAI client. Clients do not send any OpenAI key.
- Set `OPENAI_API_KEY` in the API server environment. If it’s missing, chat requests will fail.
- Client authentication (if enabled) is via `X-API-Key` or `Authorization: Bearer <token>` — not by passing an OpenAI key.

### Run MCP over HTTP Server (for Claude/MCP clients) ✨ **UPDATED**
```bash
python scripts/run_mcp_server.py
# Available at http://127.0.0.1:8081
# MCP Endpoint: POST /mcp (JSON-RPC)
# SSE Endpoint: GET /mcp/sse (Server-Sent Events)
# Health Check: GET /health
```

## MCP over HTTP Protocol ✨ **NEW SECTION**

### Endpoints

**Primary MCP Endpoint:**
- `POST /mcp` - JSON-RPC 2.0 endpoint for all MCP operations

**Streaming Endpoint:**
- `GET /mcp/sse` - Server-Sent Events for real-time data streaming

**Utility Endpoints:**
- `GET /health` - Server health check and capabilities

### Supported MCP Methods

**Core Protocol:**
- `initialize` - Server initialization and capability negotiation
- `tools/list` - Enumerate available tools
- `tools/call` - Execute specific tools with arguments
- `resources/list` - List available resources
- `resources/read` - Read specific resource data

### Example JSON-RPC Requests

**Initialize Server:**
```json
POST /mcp
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {
      "name": "claude",
      "version": "1.0.0"
    }
  }
}
```

**List Available Tools:**
```json
POST /mcp
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

**Call a Tool:**
```json
POST /mcp
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "search_profiles",
    "arguments": {
      "query": "test",
      "limit": 10
    }
  }
}
```

## Usage (Advanced)

```bash
# Show help
poetry run python -m nostr_market_mcp --help

# Initialize the database
poetry run python -m nostr_market_mcp migrate

# Add sample profile data for testing
poetry run python -m nostr_market_mcp add-sample-data

# Start the MCP over HTTP server only
poetry run python -m nostr_market_mcp serve --host 0.0.0.0 --port 8000

# Run the Nostr profile ingestion worker only (monitors all profiles)
poetry run python -m nostr_market_mcp ingest

# Run ingestion for a specific pubkey
poetry run python -m nostr_market_mcp ingest --pubkey npub1... --relays wss://relay1.com,wss://relay2.com

# Run both server and ingestion worker together
poetry run python -m nostr_market_mcp run --pubkey npub1... --relays wss://relay1.com,wss://relay2.com
```

## MCP Tools (via JSON-RPC) ✨ **UPDATED**

The MCP server provides the following tools accessible via the `tools/call` JSON-RPC method:

### Profile Tools
- `search_profiles` - Search profiles by content (name, about, nip05, etc.)
- `get_profile_by_pubkey` - Get a specific profile by pubkey
- `list_all_profiles` - List all profiles with pagination
- `get_profile_stats` - Get statistics about profiles in the database
- `search_business_profiles` - **NEW**: Search for business profiles with filtering by business type
- `get_business_types` - **NEW**: Get available business type filters
- `explain_profile_tags` - **NEW**: Parse and explain profile tags in human-readable format

### System Tools
- `refresh_profiles_from_nostr` - **NEW**: Manually trigger database refresh from Nostr relays
- `get_refresh_status` - **NEW**: Get status of automatic refresh system
- `clear_database` - Clear all profiles (test utility)

## MCP Resources (via JSON-RPC) ✨ **UPDATED**

Resources are accessible via the `resources/read` JSON-RPC method:

### Resource URI Patterns

- Profile by pubkey: `nostr://{pubkey}/profile`
- Stalls by merchant pubkey: `nostr://{pubkey}/stalls`
- Specific stall: `nostr://{pubkey}/stall/{d_tag}`
- Product catalog by merchant: `nostr://{pubkey}/catalog`
- Specific product: `nostr://{pubkey}/product/{d_tag}`

## Example Profile Structure

Profiles stored and returned follow the Nostr NIP-01 metadata format:

```json
{
  "pubkey": "57d03534460df449321cde3757b1b379a8377bace8199101df0716e20dbb7991",
  "name": "test",
  "display_name": "Test Unit", 
  "about": "Testing for the sake of testing...",
  "picture": "https://blossom.band/650ccd2a489b3717566a67bbabbbf32f28f2b458d39a3f155d998a00f2aab8a8",
  "banner": "https://blossom.band/f2a00732b50318b2230917863377eef95edc32a7d93d4165054a466ca46535f9",
  "website": "https://www.synvya.com",
  "nip05": "test@synvya.com",
  "bot": false
}
```

## Development

```bash
# Install dev dependencies
poetry install --with dev

# Run tests
poetry run pytest

# Run MCP integration tests ✨ NEW
pytest tests/test_mcp_integration.py -v

# Run linting
poetry run ruff check .
poetry run black --check .
poetry run mypy .
```

## Configuration

### MCP Authentication ✨ **UPDATED**

Authentication can be enabled by setting the `MCP_BEARER` environment variable. If set, all requests to the MCP endpoints will require the Bearer token in the Authorization header.

```bash
export MCP_BEARER=your_secret_token
```

**Example authenticated request:**
```bash
curl -X POST http://localhost:8081/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_secret_token" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

### Server-Sent Events ✨ **NEW**

Enable real-time streaming via SSE:

```bash
curl -N http://localhost:8081/mcp/sse
```

## Architecture

The system consists of three main components:

1. **Ingestion Worker** (`nostr_market_mcp.ingest`): Subscribes to Nostr relays and ingests profile events
2. **Database** (`nostr_market_mcp.db`): SQLite database with profile storage and search capabilities  
3. **MCP over HTTP Server** (`src.mcp.server`): HTTP server exposing MCP-compatible JSON-RPC endpoints ✨ **UPDATED**

Profile events are stored using replaceable event logic where kind+pubkey serves as the primary key, keeping the newest event by `created_at` timestamp.

## Automatic Refresh Configuration

The server automatically searches for business profiles on these default relays:
- `wss://relay.damus.io`
- `wss://nos.lol`
- `wss://relay.snort.social`
- `wss://nostr.wine`
- `wss://relay.nostr.band`

**Refresh Schedule**: Every 5 minutes (300 seconds)

**Target Profiles**: kind:0 profiles that contain:
- Tag "L" with value "business.type"

## Testing ✨ **UPDATED**

### Unit Tests (Mocked Database)
```bash
# Run MCP unit tests
python tests/run_mcp_tests.py

# Run API tests  
python tests/run_tests.py
```

### Integration Tests (Real Server)
```bash
# Run MCP integration tests with real server
pytest tests/test_mcp_integration.py -v

# Run all tests
pytest tests/ -v
```

**Test Coverage:**
- **49 total tests**: 23 API + 14 MCP unit + 12 MCP integration
- **MCP Protocol Compliance**: 100% JSON-RPC compatibility
- **Claude Integration**: Full compatibility testing
- **SSE Streaming**: Real-time data streaming tests
