#!/bin/bash
#
# Run all local service tests.
#
# This script runs tests for all three services in sequence.
#

set -e

echo "🚀 Running All Local Service Tests"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Make scripts executable
chmod +x tests/run_database_local_tests.sh
chmod +x tests/run_api_local_tests.sh
chmod +x tests/run_mcp_local_tests.sh

# Track test results
TESTS_PASSED=0
TESTS_FAILED=0

run_test_suite() {
    local test_name="$1"
    local test_script="$2"
    
    echo -e "\n${BLUE}🏃 Running $test_name...${NC}"
    echo "$(printf '=%.0s' {1..50})"
    
    if bash "$test_script"; then
        echo -e "${GREEN}✅ $test_name PASSED${NC}"
        TESTS_PASSED=$((TESTS_PASSED + 1))
    else
        echo -e "${RED}❌ $test_name FAILED${NC}"
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi
}

# Run all test suites
run_test_suite "Database Service Tests" "tests/run_database_local_tests.sh"
run_test_suite "API Service Tests" "tests/run_api_local_tests.sh"
run_test_suite "MCP Service Tests" "tests/run_mcp_local_tests.sh"

# Summary
echo -e "\n${BLUE}📊 Test Results Summary${NC}"
echo "$(printf '=%.0s' {1..50})"
echo -e "Tests Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Tests Failed: ${RED}$TESTS_FAILED${NC}"

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "\n${GREEN}🎉 All local service tests passed!${NC}"
    echo -e "${GREEN}The 3-service architecture is working correctly.${NC}"
    exit 0
else
    echo -e "\n${RED}💥 Some tests failed. Please check the output above.${NC}"
    exit 1
fi
