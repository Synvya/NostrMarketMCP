#!/bin/bash
#
# Run local API service tests.
#
# This script:
# 1. Starts the database service
# 2. Starts the API service 
# 3. Runs the API service tests
# 4. Cleans up the services
#

set -e

echo "🚀 Starting API Service Local Tests"
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
    
    # Kill API service
    if [ ! -z "$API_PID" ]; then
        echo "Stopping API service (PID: $API_PID)"
        kill $API_PID 2>/dev/null || true
        wait $API_PID 2>/dev/null || true
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

# Skip pytest check for now - assume environment is properly set up

# Set environment variables
export ENVIRONMENT=test
export DATABASE_PATH="$PROJECT_ROOT/test_database.db"
export DATABASE_SERVICE_URL="http://localhost:8082"
# Prevent modules from self-starting extra servers when imported
export RUN_STANDALONE=0

# Disable authentication for testing by unsetting auth variables
unset API_KEY
unset BEARER_TOKEN
unset OPENAI_API_KEY
export API_KEY=""
export BEARER_TOKEN=""
export OPENAI_API_KEY=""

echo -e "${YELLOW}📦 Starting Database Service...${NC}"
python3 scripts/run_database_service.py &
DATABASE_PID=$!
echo "Database service started (PID: $DATABASE_PID)"

# Wait for database service to be ready
echo "Waiting for database service to be ready..."
for i in {1..30}; do
    if curl -s http://127.0.0.1:8082/health > /dev/null 2>&1 || curl -s http://localhost:8082/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Database service is ready${NC}"
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ Database service failed to start${NC}"
        exit 1
    fi
    sleep 2
done

echo -e "${YELLOW}🌐 Starting API Service...${NC}"
python3 scripts/run_api_service.py &
API_PID=$!
echo "API service started (PID: $API_PID)"

# Wait for API service to be ready
echo "Waiting for API service to be ready..."
for i in {1..30}; do
    # Try multiple endpoints to ensure service is responding
    if curl -s http://127.0.0.1:8080/health > /dev/null 2>&1 || curl -s http://localhost:8080/health > /dev/null 2>&1; then
        echo -e "${GREEN}✅ API service is ready${NC}"
        # Give the service a little extra time to fully initialize
        echo "Waiting additional 3 seconds for service to fully initialize..."
        sleep 3
        break
    fi
    if [ $i -eq 30 ]; then
        echo -e "${RED}❌ API service failed to start${NC}"
        # Debug: show what's actually running
        echo "Debug: Processes on port 8080:"
        lsof -i:8080 || echo "No processes found on port 8080"
        exit 1
    fi
    echo "Attempt $i/30 - waiting for API service..."
    sleep 2
done

echo -e "${YELLOW}🧪 Running API Service Tests...${NC}"
python3 -m pytest tests/test_api_service_local.py -v --tb=short

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ All API service tests passed!${NC}"
else
    echo -e "${RED}❌ Some API service tests failed${NC}"
    exit 1
fi

echo -e "${GREEN}🎉 API Service Local Tests Completed Successfully!${NC}"
