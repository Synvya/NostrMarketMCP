# NostrProfileMCP

Bridge that turns Nostr profile events into an MCP server for AI agents with automatic business profile discovery.

## Overview

NostrMarketMCP ingests Nostr profile events (kind 0) and marketplace stalls (kind 30017), persists them in a SQLite database, and exposes them as resources and tools via an HTTP MCP-compatible server. This allows AI agents to interact with Nostr profile information, marketplace stalls, search profiles and stalls, and analyze user data.

**NEW:** The server now automatically refreshes its database with business profiles from Nostr relays at startup and every 5 minutes, specifically targeting profiles with "L" "business.type" tags.

## Features

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

## Usage

```bash
# Show help
poetry run python -m nostr_market_mcp --help

# Initialize the database
poetry run python -m nostr_market_mcp migrate

# Add sample profile data for testing
poetry run python -m nostr_market_mcp add-sample-data

# Start the MCP server only
poetry run python -m nostr_market_mcp serve --host 0.0.0.0 --port 8000

# Run the Nostr profile ingestion worker only (monitors all profiles)
poetry run python -m nostr_market_mcp ingest

# Run ingestion for a specific pubkey
poetry run python -m nostr_market_mcp ingest --pubkey npub1... --relays wss://relay1.com,wss://relay2.com

# Run both server and ingestion worker together
poetry run python -m nostr_market_mcp run --pubkey npub1... --relays wss://relay1.com,wss://relay2.com
```

## API Endpoints

The MCP server provides the following endpoints:

### Resources

- `GET /mcp/profiles/{pubkey}` - Get a specific profile by pubkey
- `GET /mcp/stalls/{pubkey}` - Get all stalls for a specific merchant by pubkey
- `GET /mcp/stall/{pubkey}/{d_tag}` - Get a specific stall by pubkey and d-tag
- `GET /mcp/products/{pubkey}` - **NEW**: Get all products for a specific merchant by pubkey
- `GET /mcp/product/{pubkey}/{d_tag}` - **NEW**: Get a specific product by pubkey and d-tag

### Tools (POST endpoints)

#### Profile Tools
- `/mcp/tools/search_profiles` - Search profiles by content (name, about, nip05, etc.)
- `/mcp/tools/get_profile_by_pubkey` - Get a specific profile by pubkey
- `/mcp/tools/list_all_profiles` - List all profiles with pagination
- `/mcp/tools/get_profile_stats` - Get statistics about profiles in the database
- `/mcp/tools/search_business_profiles` - **NEW**: Search for business profiles with filtering by business type
- `/mcp/tools/get_business_types` - **NEW**: Get available business type filters
- `/mcp/tools/explain_profile_tags` - **NEW**: Parse and explain profile tags in human-readable format

#### Stall Tools
- `/mcp/tools/search_stalls` - **NEW**: Search marketplace stalls by content (name, description)
- `/mcp/tools/list_all_stalls` - **NEW**: List all stalls with pagination
- `/mcp/tools/get_stall_by_pubkey_and_dtag` - **NEW**: Get a specific stall by pubkey and d-tag
- `/mcp/tools/get_stall_stats` - **NEW**: Get statistics about stalls in the database

#### Product Tools
- `/mcp/tools/search_products` - **NEW**: Search marketplace products by content (name, description)
- `/mcp/tools/list_all_products` - **NEW**: List all products with pagination
- `/mcp/tools/get_product_by_pubkey_and_dtag` - **NEW**: Get a specific product by pubkey and d-tag
- `/mcp/tools/get_product_stats` - **NEW**: Get statistics about products in the database

#### System Tools
- `/mcp/tools/refresh_profiles_from_nostr` - **NEW**: Manually trigger database refresh from Nostr relays
- `/mcp/tools/get_refresh_status` - **NEW**: Get status of automatic refresh system

### Info

- `GET /mcp/info` - Get server information and capabilities

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

# Run linting
poetry run ruff check .
poetry run black --check .
poetry run mypy .
```

## Resource URI Patterns

- Profile by pubkey: `nostr://{pubkey}/profile`
- Stalls by merchant pubkey: `nostr://{pubkey}/stalls`
- Specific stall: `nostr://{pubkey}/stall/{d_tag}`
- Product catalog by merchant: `nostr://{pubkey}/catalog`
- Specific product: `nostr://{pubkey}/product/{d_tag}`

## Configuration

Authentication can be enabled by setting the `MCP_BEARER` environment variable. If set, all requests to the MCP endpoints will require the Bearer token in the Authorization header.

```bash
export MCP_BEARER=your_secret_token
```

## Architecture

The system consists of three main components:

1. **Ingestion Worker** (`nostr_market_mcp.ingest`): Subscribes to Nostr relays and ingests profile events
2. **Database** (`nostr_market_mcp.db`): SQLite database with profile storage and search capabilities  
3. **MCP Server** (`nostr_market_mcp.server`): HTTP server exposing MCP-compatible endpoints for profile access

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

You can check the refresh status and manually trigger refreshes using the new MCP tools.

## Business Profile Tags

Business profiles are identified by the following tag structure:
```json
{
  "tags": [
    ["L", "business.type"],
    ["l", "restaurant"],  // Business type: retail, restaurant, services, business, entertainment, other
    ["t", "food"],        // Optional business category tags
    // ... other tags
  ]
}
```
