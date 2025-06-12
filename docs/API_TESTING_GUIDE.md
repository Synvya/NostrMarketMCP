# API Tests

This directory contains comprehensive automated tests for the Nostr Profiles API.

## Test Files

- **`test_api_endpoints.py`** - Main API endpoint tests covering all functionality
- **`test_db.py`** - Database tests (existing)
- **`test_server.py`** - Server tests (existing)
- **`conftest.py`** - Test configuration and fixtures (existing)

## Running Tests

### Prerequisites

1. **Start the API server**:
   ```bash
   python run_local.py
   ```

2. **Ensure dependencies are installed**:
   ```bash
   pip install -r requirements.txt
   ```

### Run All API Tests

```bash
# Using the test runner (recommended)
python run_tests.py

# Using pytest directly
pytest tests/test_api_endpoints.py -v
```

### Run Specific Tests

```bash
# Test a specific test class
pytest tests/test_api_endpoints.py::TestAPIEndpoints -v

# Test a specific test method
pytest tests/test_api_endpoints.py::TestAPIEndpoints::test_health_check -v

# Using the test runner for specific tests
python run_tests.py TestAPIEndpoints::test_health_check
```

### Run All Tests

```bash
# Run all tests in the tests directory
pytest tests/ -v
```

## Test Coverage

The API endpoint tests cover:

### ✅ Core Endpoints
- `GET /health` - Health check
- `POST /api/search_profiles` - Profile search
- `POST /api/search_business_profiles` - Business profile search
- `GET /api/profile/{pubkey}` - Get specific profile
- `GET /api/stats` - Database statistics
- `GET /api/business_types` - Available business types
- `POST /api/refresh` - Manual database refresh

### ✅ Security Tests
- Authentication validation (API key required)
- Input validation and sanitization
- SQL injection protection
- Large payload protection
- Security headers verification
- CORS configuration

### ✅ Error Handling
- Invalid input handling
- Missing authentication
- Malformed JSON
- Invalid data types
- Rate limiting structure

### ✅ Integration Tests
- End-to-end data flow (refresh → search → stats)
- Response format consistency
- Database state verification

## Test Configuration

Tests use the following configuration:
- **Server URL**: `http://127.0.0.1:8080`
- **API Key**: `local_test_api_key`
- **Timeout**: 30 seconds
- **Test Profile**: `57d03534460df449321cde3757b1b379a8377bace8199101df0716e20dbb7991`

## Expected Test Results

When all tests pass, you should see:
- ✅ All API endpoints respond correctly
- ✅ Authentication is enforced
- ✅ Input validation works
- ✅ Security headers are present
- ✅ Data flow is consistent

## Troubleshooting

### Common Issues

1. **Server not running**:
   ```
   ❌ ERROR: API server is not running!
   ```
   **Solution**: Start the server with `python run_local.py`

2. **Authentication failures**:
   ```
   AssertionError: assert 401 == 200
   ```
   **Solution**: Check that `API_KEY=local_test_api_key` is set in environment

3. **Timeout errors**:
   ```
   httpx.TimeoutException
   ```
   **Solution**: Ensure server is responding and not overloaded

4. **Database empty**:
   ```
   Profile not found
   ```
   **Solution**: Run manual refresh: `curl -X POST http://127.0.0.1:8080/api/refresh -H "X-API-Key: local_test_api_key"`

## Continuous Integration

These tests are designed to be run in CI/CD pipelines. They:
- Start and stop HTTP clients cleanly
- Handle missing data gracefully
- Provide clear failure messages
- Run independently without side effects 