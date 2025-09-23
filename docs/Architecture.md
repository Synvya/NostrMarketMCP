# Architecture

## Summary (Plain English)

NostrMarketMCP is split into three small services that each do one job well:

- Database Service (the source of truth): Collects and stores Nostr profile data and serves it over a simple HTTP API. Think of it as the library where all the information lives.
- API Service (for apps): A secure, developer‑friendly HTTP API that apps or backends call to search and fetch profiles. It never stores data itself; it always asks the Database Service.
- MCP Service (for AI tools): An MCP (Model Context Protocol) server that exposes the same profile data to AI agents and tools in a way they understand. It also asks the Database Service for everything.

All three can run in separate containers (e.g., on AWS ECS). The API and MCP services do not talk to each other; both talk to the Database Service. This keeps things simpler, safer, and easier to scale: we can update one service without touching the others, and we always have a single, consistent source of truth.

## Technical Overview

- Services and Ports
  - Database Service (HTTP): `:8082`
  - API Service (FastAPI): `:8080`
  - MCP Service (FastAPI + MCP over HTTP/SSE): `:8081`

- Responsibilities
  - Database Service
    - Stores Nostr data as events (SQLite under the hood) and exposes read/search endpoints: `/health`, `/stats`, `/search`, `/business-types`, `/profile/{pubkey}`, `/refresh`.
    - Refresh task fetches/derives merchant profiles (from relays and metadata); in test mode, refresh is a quick no‑op for speed.
  - API Service
    - Public‑facing HTTP API with security, validation, and stable response models; delegates all data reads and refresh to the Database Service via HTTP.
    - Chat endpoint runs a deterministic tool loop against OpenAI (server‑side) when `OPENAI_API_KEY` is configured.
  - MCP Service
    - Exposes tools (search, stats, business types, refresh) via MCP JSON‑RPC and an SSE endpoint; uses the same database client as the API.

- Data Access Layer
  - Single shared client: `src/shared/database_client.py` (used by API and MCP wrappers).
  - API adapter: `src/api/database_adapter.py` provides a thin, stable interface for endpoints.

- Security (API Service)
  - Auth: API key (`X-API-Key` or `?api_key=`) and/or Bearer token. In production, credentials must be long and present.
  - CORS: Explicit `ALLOWED_ORIGINS` plus `https://platform.openai.com`; disabled in test.
  - Middleware: Basic request checks, in‑memory rate limiting, and security headers; disabled in test.
  - Input validation: Pydantic models and sanitization for queries, pubkeys, and chat messages.

- Environments & Config
  - `ENVIRONMENT` controls behavior (`development`, `test`, `production`).
  - Service discovery: `DATABASE_SERVICE_URL` is how API/MCP find the Database Service (e.g., `http://nostr-database:8082` on ECS).
  - Chat requires server‑side `OPENAI_API_KEY`.

- Runtime Behavior
  - API/MCP never write directly; they forward `/refresh` to the Database Service.
  - SSE: MCP exposes `/mcp/sse` for event streams; clients should use streaming reads.
  - Tests: local scripts start services, wait for `/health`, then run pytest. In test mode, heavy network work is skipped and ports are guarded.

- Deployment Notes (AWS ECS)
  - Three independent tasks/services with network policies so only API/MCP can reach the Database Service.
  - Health checks hit `/health` on each service.
  - Scale API/MCP independently of the Database Service; keep state in the database (SQLite file or externalized volume, as needed).

