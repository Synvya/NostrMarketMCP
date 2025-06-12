# MCP Server Testing Guide

This guide covers testing the **Model Context Protocol (MCP) Server** for the Nostr Profiles project.

## Overview

The MCP server provides tools and resources for accessing Nostr profile data through the Model Context Protocol. It exposes various functions that can be called by MCP clients (like AI assistants) to search, retrieve, and analyze Nostr profiles, stalls, and products.

## Test Files

- **`tests/test_mcp_server.py`** - Comprehensive MCP server tests
- **`tests/run_mcp_tests.py`** - Test runner for MCP server tests

## MCP Tools Being Tested

### 📊 Profile Tools
- `search_profiles(query, limit)` - Search for profiles by content
- `get_profile_by_pubkey(pubkey)` - Get specific profile by public key
- `list_all_profiles(offset, limit)` - List all profiles with pagination
- `get_profile_stats()` - Get profile database statistics
- `search_business_profiles(query, business_type, limit)` - Search business profiles
- `get_business_types()` - Get available business types
- `explain_profile_tags(tags_json)` - Explain profile tags

### 🏪 Stall Tools
- `search_stalls(query, pubkey, limit)` - Search for marketplace stalls
- `list_all_stalls(offset, limit)` - List all stalls with pagination
- `get_stall_by_pubkey_and_dtag(pubkey, d_tag)` - Get specific stall
- `get_stall_stats()` - Get stall statistics

### 🛍️ Product Tools
- `search_products(query, pubkey, limit)` - Search for products
- `list_all_products(offset, limit)` - List all products with pagination
- `get_product_by_pubkey_and_dtag(pubkey, d_tag)` - Get specific product
- `get_product_stats()` - Get product statistics

### 🔧 Utility Tools
- `refresh_profiles_from_nostr()` - Trigger manual database refresh
- `get_refresh_status()` - Get refresh task status
- `clear_database()` - Clear all database data

### 📄 Resources
- `nostr://profiles/{pubkey}` - Profile resource endpoint
- `nostr://stalls/{pubkey}` - Stalls resource endpoint
- `nostr://stall/{pubkey}/{d_tag}` - Single stall resource endpoint
- `nostr://products/{pubkey}` - Products resource endpoint
- `nostr://product/{pubkey}/{d_tag}` - Single product resource endpoint

## Running Tests

### Prerequisites

No server startup required - tests use mocked database!

```bash
# Ensure dependencies are installed
pip install -r requirements.txt
```

### Run All MCP Tests

```bash
# Using the MCP test runner (recommended)
cd tests && python run_mcp_tests.py
```

# Using pytest directly
```bash
pytest tests/test_mcp_server.py -v
```

### Run Specific Tests

```bash
# Test a specific test class
pytest tests/test_mcp_server.py::TestMCPServer -v

# Test a specific test method
pytest tests/test_mcp_server.py::TestMCPServer::test_search_profiles_success -v

# Using the test runner for specific tests
python run_mcp_tests.py TestMCPServer::test_search_profiles_success
```

## Test Coverage

### ✅ Tool Function Tests
- **Success cases**: Valid inputs, expected outputs
- **Edge cases**: Empty results, missing data
- **Error handling**: Invalid inputs, database errors
- **Pagination**: Offset/limit functionality
- **Search functionality**: Query matching, filtering

### ✅ Resource Tests
- **Profile resources**: Individual profile data retrieval
- **Stall resources**: Marketplace stall data
- **Product resources**: Product catalog data
- **URI parsing**: Proper resource URI handling

### ✅ Database Integration
- **Mock database**: Realistic data simulation
- **Database errors**: Connection failures, query errors
- **Data consistency**: Proper data formatting
- **Async operations**: Proper async/await handling

### ✅ JSON Response Validation
- **Response format**: Consistent JSON structure
- **Success responses**: Proper success flags and data
- **Error responses**: Clear error messages
- **Data types**: Correct data type validation

## Mock Database

The tests use a `MockDatabase` class that simulates real database operations:

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

## Example Test Run

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

## Troubleshooting

### Common Issues

1. **Import errors**:
   ```
   ModuleNotFoundError: No module named 'nostr_profiles_mcp_server'
   ```
   **Solution**: Run tests from project root directory

2. **Mock import issues**:
   ```
   ImportError: cannot import name 'synvya_sdk'
   ```
   **Solution**: Tests use mocks automatically when synvya_sdk unavailable

3. **Async test issues**:
   ```
   TypeError: object 'coroutine' is not callable
   ```
   **Solution**: Ensure proper async/await usage in tests

4. **Database state issues**:
   ```
   AssertionError: Database not properly cleaned
   ```
   **Solution**: Each test uses fresh MockDatabase instance

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