# Testing Guide for NostrMarketMCP 3-Service Architecture

This directory contains comprehensive tests for the new 3-service architecture:
- **Database Service** (port 8082) - Handles data ingestion and storage
- **API Service** (port 8080) - Provides REST API for external clients  
- **MCP Service** (port 8081) - Provides MCP protocol interface

## Test Structure

### Local Tests (`test_*_local.py`)
These tests run against services started locally and are used for development and CI/CD.

- `test_database_service_local.py` - Tests database service endpoints
- `test_api_service_local.py` - Tests API service endpoints  
- `test_mcp_service_local.py` - Tests MCP service endpoints

### AWS Tests (`test_*_aws.py`)
These tests run against services deployed on AWS and are used for production validation.

- `test_database_service_aws.py` - Tests database service on AWS
- `test_api_service_aws.py` - Tests API service on AWS
- `test_mcp_service_aws.py` - Tests MCP service on AWS

### Service Launcher Scripts (`../scripts/run_*_service.py`)
Scripts to start individual services locally for testing:

- `run_database_service.py` - Starts database service on port 8082
- `run_api_service.py` - Starts API service on port 8080  
- `run_mcp_service.py` - Starts MCP service on port 8081

### Test Runner Scripts (`run_*_tests.sh`)
Automated test runners that start services and run tests:

- `run_database_local_tests.sh` - Database service tests
- `run_api_local_tests.sh` - API service tests (starts database + API)
- `run_mcp_local_tests.sh` - MCP service tests (starts database + MCP)
- `run_all_local_tests.sh` - Runs all local tests in sequence

## Quick Start

### Prerequisites
```bash
pip install pytest pytest-asyncio httpx
```

### Running All Local Tests
```bash
# Run all services and tests
./tests/run_all_local_tests.sh
```

### Running Individual Service Tests
```bash
# Database service only
./tests/run_database_local_tests.sh

# API service (includes database)  
./tests/run_api_local_tests.sh

# MCP service (includes database)
./tests/run_mcp_local_tests.sh
```

### Manual Testing
```bash
# Start database service
python3 scripts/run_database_service.py

# Start API service (in another terminal)
python3 scripts/run_api_service.py

# Start MCP service (in another terminal)  
python3 scripts/run_mcp_service.py

# Run specific tests
python3 -m pytest tests/test_api_service_local.py -v
```

## AWS Testing

### Setup
Set environment variables for AWS testing:
```bash
export AWS_API_SERVICE_URL="https://your-api-gateway.amazonaws.com"
export AWS_API_KEY="your-api-key"
export AWS_MCP_SERVICE_URL="http://nostr-mcp:8081"  # Internal VPC URL
```

### Running AWS Tests
```bash
# API service on AWS
python3 -m pytest tests/test_api_service_aws.py -v

# MCP service on AWS (must run from within VPC)
python3 -m pytest tests/test_mcp_service_aws.py -v

# Database service on AWS (must run from within VPC)
python3 -m pytest tests/test_database_service_aws.py -v
```

## Test Coverage

### Database Service Tests
- Health check endpoint
- Statistics endpoint
- Profile search functionality
- Business profile search
- Profile retrieval by pubkey
- Business types listing
- Manual refresh capability
- Pagination support

### API Service Tests
- All REST API endpoints
- Authentication and security
- Error handling and validation
- Performance testing
- CORS configuration
- Rate limiting
- Chat functionality (basic structure)

### MCP Service Tests  
- MCP protocol compliance
- All MCP tools functionality
- JSON-RPC request/response handling
- Server-Sent Events support
- Error handling
- Performance testing

## Architecture Validation

These tests validate the 3-service architecture by ensuring:

1. **Service Isolation** - Each service can start independently
2. **HTTP Communication** - Services communicate via HTTP APIs
3. **Database Independence** - Only database service accesses SQLite directly
4. **Dependency Management** - Nostr dependencies only in database service
5. **Error Handling** - Proper error propagation between services
6. **Performance** - Acceptable response times with service overhead

## Continuous Integration

For CI/CD pipelines:

```bash
# Local testing in CI
./tests/run_all_local_tests.sh

# AWS testing after deployment
python3 -m pytest tests/test_api_service_aws.py -v
```

## Troubleshooting

### Services Won't Start
- Check if ports 8080, 8081, 8082 are available
- Verify Python dependencies are installed
- Check environment variables are set correctly

### Tests Failing
- Ensure services are fully started (health checks pass)
- Check service logs for errors
- Verify database has data (some tests expect real data)

### AWS Tests Failing
- Verify AWS services are deployed and running
- Check environment variables for AWS URLs
- Ensure you're testing from correct network context (VPC for internal services)

## Development Workflow

1. Make code changes
2. Run relevant local tests: `./tests/run_api_local_tests.sh`
3. Run all local tests: `./tests/run_all_local_tests.sh`  
4. Deploy to AWS
5. Run AWS tests: `python3 -m pytest tests/test_api_service_aws.py -v`

This ensures both local development and production deployment are working correctly.
