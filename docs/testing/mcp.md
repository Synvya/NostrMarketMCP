# MCP Server Testing Guide

This guide covers testing the **Model Context Protocol (MCP) over HTTP Server** for the Nostr Profiles project.

## Overview

The MCP server provides tools and resources for accessing Nostr profile data through the **Model Context Protocol over HTTP**. It exposes various functions that can be called by MCP clients (like Claude) to search, retrieve, and analyze Nostr profiles using **JSON-RPC over HTTP** with optional **Server-Sent Events (SSE) streaming**.

**🚀 NEW: MCP over HTTP Implementation**
- **Streamable HTTP**: Single HTTP endpoint accepting JSON-RPC POSTs with SSE streaming responses
- **Claude Compatible**: Full MCP protocol compliance for Claude and other MCP clients
- **JSON-RPC Protocol**: Proper MCP over HTTP transport instead of stdio
- **Real-time Streaming**: Server-Sent Events support for live data streaming

## Test Files

- **`tests/test_mcp_server.py`** - Unit tests with mocked database (14 tests)
- **`tests/test_mcp_integration.py`** - Integration tests with real server (12 tests) ✨ **NEW**
- **`tests/run_mcp_tests.py`** - Test runner for unit tests

## MCP Tools Being Tested

### 📊 Profile Tools (via JSON-RPC)
- `search_profiles(query, limit)` - Search for profiles by content
- `get_profile_by_pubkey(pubkey)` - Get specific profile by public key
- `list_all_profiles(offset, limit)` - List all profiles with pagination
- `get_profile_stats()` - Get profile database statistics
- `search_business_profiles(query, business_type, limit)` - Search business profiles
- `get_business_types()` - Get available business types
- `explain_profile_tags(tags_json)` - Explain profile tags

### 🔧 Utility Tools
- `refresh_profiles_from_nostr()` - Trigger manual database refresh
- `get_refresh_status()` - Get refresh task status
- `clear_database()` - Clear all database data

### 📄 MCP Protocol Methods ✨ **NEW**
- `initialize` - Server initialization and capability negotiation
- `tools/list` - Enumerate available tools
- `tools/call` - Execute specific tools with arguments
- `resources/list` - List available resources
- `resources/read` - Read specific resource data

### 📄 Resources
- `nostr://profiles/{pubkey}` - Profile resource endpoint
- `nostr://stalls/{pubkey}` - Stalls resource endpoint
- `nostr://stall/{pubkey}/{d_tag}` - Single stall resource endpoint
- `nostr://products/{pubkey}` - Products resource endpoint
- `nostr://product/{pubkey}/{d_tag}` - Single product resource endpoint

## Running Tests

### Prerequisites

```bash
# Ensure dependencies are installed
pip install -r requirements.txt
```

### Run Unit Tests (Mocked Database)

```bash
# Using the MCP test runner (recommended)
cd tests && python run_mcp_tests.py

# Using pytest directly
pytest tests/test_mcp_server.py -v
```

### Run Integration Tests (Real MCP over HTTP Server) ✨ **NEW**

```bash
# Run all integration tests
pytest tests/test_mcp_integration.py -v

# Run specific integration test
pytest tests/test_mcp_integration.py::TestMCPServerIntegration::test_list_tools -v

# Run with verbose server output
pytest tests/test_mcp_integration.py -v -s
```

### Run All MCP Tests

```bash
# Run both unit and integration tests
pytest tests/test_mcp_server.py tests/test_mcp_integration.py -v

# Or run separately
python run_mcp_tests.py && pytest tests/test_mcp_integration.py -v
```

### Run Specific Tests

```bash
# Test a specific unit test class
pytest tests/test_mcp_server.py::TestMCPServer -v

# Test a specific unit test method
pytest tests/test_mcp_server.py::TestMCPServer::test_search_profiles_success -v

# Test a specific integration test
pytest tests/test_mcp_integration.py::TestMCPServerIntegration::test_server_connection -v
```

## Test Coverage

### ✅ Unit Tests (Mocked Database)
- **Success cases**: Valid inputs, expected outputs
- **Edge cases**: Empty results, missing data
- **Error handling**: Invalid inputs, database errors
- **Pagination**: Offset/limit functionality
- **Search functionality**: Query matching, filtering

### ✅ Integration Tests (Real Server) ✨ **NEW**
- **Server lifecycle**: Startup, cleanup, process management
- **JSON-RPC Protocol**: Proper MCP over HTTP transport
- **Tool execution**: Real tool calls via `tools/call` method
- **Resource access**: Resource listing and reading
- **Error handling**: Protocol errors, malformed requests
- **Concurrent access**: Multiple simultaneous requests
- **SSE Streaming**: Server-Sent Events functionality

### ✅ MCP Protocol Compliance ✨ **NEW**
- **Initialization**: Proper capability negotiation
- **Tool listing**: Complete tool enumeration
- **Tool calling**: Argument passing and result handling
- **Resource management**: URI-based resource access
- **Error responses**: Standard JSON-RPC error format

### ✅ Database Integration
- **Mock database**: Realistic data simulation (unit tests)
- **Real database**: Actual SQLite operations (integration tests)
- **Database errors**: Connection failures, query errors
- **Data consistency**: Proper data formatting
- **Async operations**: Proper async/await handling

### ✅ JSON Response Validation
- **Response format**: Consistent JSON-RPC structure
- **Success responses**: Proper success flags and data
- **Error responses**: Clear error messages
- **Data types**: Correct data type validation

## MCP over HTTP Architecture ✨ **NEW SECTION**

### Protocol Implementation
- **Transport**: HTTP with JSON-RPC 2.0
- **Endpoint**: Single `/mcp` endpoint for all MCP operations
- **Streaming**: `/mcp/sse` endpoint for Server-Sent Events
- **Authentication**: Optional Bearer token support
- **Content-Type**: `application/json` for requests
- **Response Format**: Standard JSON-RPC 2.0 responses

### Example JSON-RPC Requests

**List Tools:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/list",
  "params": {}
}
```

**Call Tool:**
```json
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

**Initialize Server:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": {
      "name": "test-client",
      "version": "1.0.0"
    }
  }
}
```

## Mock Database

The unit tests use a `MockDatabase` class that simulates real database operations:

```python
class MockDatabase:
    def __init__(self):
        self.profiles = [...]  # Test profile data
        self.stalls = [...]    # Test stall data  
        self.products = [...]  # Test product data
```

### Mock Data Structure

**Test Profile:**
```json
{
  "pubkey": "57d03534460df449321cde3757b1b379a8377bace8199101df0716e20dbb7991",
  "name": "test",
  "display_name": "Test Unit",
  "about": "Testing for the sake of testing...",
  "picture": "https://blossom.band/...",
  "website": "https://www.synvya.com",
  "nip05": "test@synvya.com",
  "business_type": "retail",
  "namespace": "business.type",
  "tags": [["L", "business.type"], ["l", "retail", "business.type"]],
  "created_at": 1749574818
}
```

## Test Scenarios

### 🔍 Search Tests
- Search with valid queries
- Search with no results
- Search with pagination limits
- Business type filtering
- Query string matching

### 📊 Stats Tests
- Profile statistics calculation
- Required fields validation
- Data type verification
- Empty database handling

### 🔄 Refresh Tests
- Manual refresh triggering
- Refresh status checking
- Database clearing
- Error handling during refresh

### ❌ Error Handling Tests
- Database not initialized
- Invalid JSON inputs
- Database connection errors
- Malformed queries
- JSON-RPC protocol errors ✨ **NEW**
- Invalid MCP method calls ✨ **NEW**

### 🌐 Integration Test Scenarios ✨ **NEW**
- Server startup and shutdown
- Real HTTP requests to `/mcp` endpoint
- JSON-RPC protocol compliance
- Tool execution with real database
- Resource access and URI handling
- Concurrent request handling
- Process cleanup and port management

## Example Test Runs

### Unit Tests
```bash
$ cd tests && python run_mcp_tests.py

🚀 Running Nostr Profiles MCP Server Tests
==================================================
🧪 Running MCP server tests...

tests/test_mcp_server.py::TestMCPServer::test_search_profiles_success PASSED
tests/test_mcp_server.py::TestMCPServer::test_search_profiles_no_results PASSED
tests/test_mcp_server.py::TestMCPServer::test_get_profile_by_pubkey_success PASSED
tests/test_mcp_server.py::TestMCPServer::test_get_profile_by_pubkey_not_found PASSED
tests/test_mcp_server.py::TestMCPServer::test_list_all_profiles PASSED
tests/test_mcp_server.py::TestMCPServer::test_get_profile_stats PASSED
tests/test_mcp_server.py::TestMCPServer::test_search_business_profiles PASSED
tests/test_mcp_server.py::TestMCPServer::test_get_business_types PASSED
tests/test_mcp_server.py::TestMCPServer::test_explain_profile_tags PASSED
tests/test_mcp_server.py::TestMCPServer::test_explain_profile_tags_invalid_json PASSED
tests/test_mcp_server.py::TestMCPServer::test_refresh_profiles_from_nostr PASSED
tests/test_mcp_server.py::TestMCPServer::test_get_refresh_status PASSED
tests/test_mcp_server.py::TestMCPServer::test_clear_database PASSED
tests/test_mcp_server.py::TestMCPServer::test_tools_without_database PASSED

🎉 All MCP server tests passed!
```

### Integration Tests ✨ **NEW**
```bash
$ pytest tests/test_mcp_integration.py -v

=========================================== test session starts ============================================
platform darwin -- Python 3.12.8, pytest-7.4.4, pluggy-1.6.0
collected 12 items

tests/test_mcp_integration.py::TestMCPServerIntegration::test_server_connection PASSED               [  8%]
tests/test_mcp_integration.py::TestMCPServerIntegration::test_list_tools PASSED                      [ 16%]
tests/test_mcp_integration.py::TestMCPServerIntegration::test_list_resources PASSED                  [ 25%]
tests/test_mcp_integration.py::TestMCPServerIntegration::test_search_profiles_tool PASSED            [ 33%]
tests/test_mcp_integration.py::TestMCPServerIntegration::test_get_profile_stats_tool PASSED          [ 41%]
tests/test_mcp_integration.py::TestMCPServerIntegration::test_get_business_types_tool PASSED         [ 50%]
tests/test_mcp_integration.py::TestMCPServerIntegration::test_explain_profile_tags_tool PASSED       [ 58%]
tests/test_mcp_integration.py::TestMCPServerIntegration::test_search_business_profiles_tool PASSED   [ 66%]
tests/test_mcp_integration.py::TestMCPServerIntegration::test_get_refresh_status_tool PASSED         [ 75%]
tests/test_mcp_integration.py::TestMCPServerIntegration::test_tool_error_handling PASSED             [ 83%]
tests/test_mcp_integration.py::TestMCPServerIntegration::test_concurrent_tool_calls PASSED           [ 91%]
tests/test_mcp_integration.py::TestMCPServerIntegration::test_server_resource_cleanup PASSED         [100%]

============================================ 12 passed in 36.85s ============================================
```

## Troubleshooting

### Common Issues

**Unit Tests:**
- **Import errors**: Ensure all dependencies are installed
- **Mock database issues**: Check mock data structure
- **Async test failures**: Verify pytest-asyncio is installed

**Integration Tests:** ✨ **NEW**
- **Port conflicts**: Tests use port 8082, ensure it's free
- **Server startup failures**: Check server logs in test output
- **JSON-RPC errors**: Verify request format and endpoint
- **Process cleanup**: Tests automatically clean up server processes

### Debug Integration Tests ✨ **NEW**
```bash
# Run with verbose server output
pytest tests/test_mcp_integration.py -v -s --tb=long

# Check for port conflicts
lsof -i :8082

# Run single integration test for debugging
pytest tests/test_mcp_integration.py::TestMCPServerIntegration::test_list_tools -v -s
```

### Performance Considerations ✨ **NEW**
- **Integration tests**: Take ~3 seconds per test for server startup
- **Unit tests**: Run in milliseconds with mocked database
- **Parallel execution**: Integration tests run sequentially to avoid port conflicts
- **Cleanup**: Automatic server process termination and port cleanup

## Integration with CI/CD

These MCP tests can be integrated into CI/CD pipelines:

### GitHub Actions Integration
```yaml
- name: Run MCP Server Tests
  run: python run_mcp_tests.py
```

### Benefits
- **No external dependencies**: Uses mocked database
- **Fast execution**: No server startup/shutdown
- **Comprehensive coverage**: Tests all MCP tools and resources
- **Error isolation**: Each test runs independently
- **Clear reporting**: Detailed test output with specific failures

The MCP server tests ensure that all tools and resources work correctly and provide the expected JSON responses for MCP clients. 