#!/bin/bash
#
# Run local MCP service tests.
#
# This script:
# 1. Starts the database service
# 2. Starts the MCP service 
# 3. Runs the MCP service tests
# 4. Cleans up the services
#

set -e

echo "🚀 Starting MCP Service Local Tests"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Cleanup function
cleanup() {
    echo -e "\n${YELLOW}🧹 Cleaning up services...${NC}"
    
    # Kill database service
    if [ ! -z "$DATABASE_PID" ]; then
        echo "Stopping database service (PID: $DATABASE_PID)"
        kill $DATABASE_PID 2>/dev/null || true
        wait $DATABASE_PID 2>/dev/null || true
    fi
    
    # Kill MCP service
    if [ ! -z "$MCP_PID" ]; then
        echo "Stopping MCP service (PID: $MCP_PID)"
        kill $MCP_PID 2>/dev/null || true
        wait $MCP_PID 2>/dev/null || true
    fi
    
    # Clean up test database
    if [ -f "test_database.db" ]; then
        rm -f test_database.db
        echo "Removed test database"
    fi
    
    echo -e "${GREEN}✅ Cleanup completed${NC}"
}

# Set up cleanup trap
trap cleanup EXIT INT TERM

# Check if required tools are installed
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 is required but not installed${NC}"
    exit 1
fi

if ! python3 -c "import pytest" 2>/dev/null; then
    echo -e "${RED}❌ pytest is required but not installed${NC}"
    echo "Install with: pip install pytest pytest-asyncio httpx"
    exit 1
fi

# Set environment variables
export ENVIRONMENT=test
export DATABASE_PATH="$PROJECT_ROOT/test_database.db"
export DATABASE_SERVICE_URL="http://localhost:8082"
# Prevent modules from self-starting extra servers when imported
export RUN_STANDALONE=0

echo -e "${YELLOW}📦 Starting Database Service...${NC}"
source ~/.venvs/aienv/bin/activate && python3 scripts/run_database_service.py &
DATABASE_PID=$!
echo "Database service started (PID: $DATABASE_PID)"

# Wait for database service to be ready
echo "Waiting for database service to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8082/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Database service is ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ Database service failed to start${NC}"
        exit 1
    fi
    sleep 2
done

echo -e "${YELLOW}🔧 Starting MCP Service...${NC}"
source ~/.venvs/aienv/bin/activate && python3 scripts/run_mcp_service.py &
MCP_PID=$!
echo "MCP service started (PID: $MCP_PID)"

# Wait for MCP service to be ready
echo "Waiting for MCP service to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:8081/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ MCP service is ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ MCP service failed to start${NC}"
        exit 1
    fi
    sleep 2
done

echo -e "${YELLOW}🧪 Running MCP Service Tests...${NC}"
source ~/.venvs/aienv/bin/activate && python3 -m pytest tests/test_mcp_service_local.py -v --tb=short

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ All MCP service tests passed!${NC}"
else
    echo -e "${RED}❌ Some MCP service tests failed${NC}"
    exit 1
fi

echo -e "${GREEN}🎉 MCP Service Local Tests Completed Successfully!${NC}"
