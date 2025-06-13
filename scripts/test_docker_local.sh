#!/bin/bash

# Local Docker Testing Script
# Tests the same container configuration that will run in ECS
#
# Usage: ./scripts/test_docker_local.sh [start|stop|logs|rebuild]

set -e

CONTAINER_NAME="nostr-api-local-test"
IMAGE_NAME="nostr-api:local"
ENV_FILE=".env"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        log_error "Environment file '$ENV_FILE' not found!"
        log_info "Create a .env file with the following variables:"
        echo "API_KEY=your_api_key_here"
        echo "BEARER_TOKEN=your_bearer_token_here"
        echo "NOSTR_KEY=your_nostr_private_key_nsec_here"
        echo "ALLOWED_ORIGINS=https://platform.openai.com,https://synvya.com"
        echo "RATE_LIMIT_REQUESTS=100"
        echo "PORT=8080"
        echo "DATABASE_PATH=/app/data/nostr_profiles.db"
        echo "ENVIRONMENT=production"
        echo "HOST=0.0.0.0"
        echo "RATE_LIMIT_WINDOW=60"
        echo "LOG_LEVEL=info"
        exit 1
    fi
}

build_image() {
    log_info "Building Docker image (same as ECS deployment)..."
    docker build -t "$IMAGE_NAME" .
    log_info "Build completed successfully!"
}

start_container() {
    check_env_file
    
    # Stop existing container if running
    if docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
        log_warn "Container $CONTAINER_NAME is already running. Stopping it first..."
        docker stop "$CONTAINER_NAME" > /dev/null
        docker rm "$CONTAINER_NAME" > /dev/null
    fi
    
    log_info "Starting container with ECS-like configuration..."
    docker run -d \
        --name "$CONTAINER_NAME" \
        -p 8080:8080 \
        --env-file "$ENV_FILE" \
        "$IMAGE_NAME"
    
    log_info "Container started successfully!"
    log_info "API available at: http://localhost:8080"
    log_info "Health check: http://localhost:8080/health"
    
    # Wait a moment and check if container is still running
    sleep 2
    if ! docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
        log_error "Container failed to start or crashed immediately!"
        log_info "Check logs with: ./scripts/test_docker_local.sh logs"
        exit 1
    fi
}

stop_container() {
    if docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
        log_info "Stopping container..."
        docker stop "$CONTAINER_NAME" > /dev/null
        docker rm "$CONTAINER_NAME" > /dev/null
        log_info "Container stopped and removed."
    else
        log_warn "Container $CONTAINER_NAME is not running."
    fi
}

show_logs() {
    if docker ps -a -q -f name="$CONTAINER_NAME" | grep -q .; then
        log_info "Container logs:"
        docker logs "$CONTAINER_NAME"
    else
        log_error "Container $CONTAINER_NAME does not exist."
    fi
}

test_health() {
    log_info "Testing health endpoint..."
    if curl -f http://localhost:8080/health > /dev/null 2>&1; then
        log_info "✅ Health check passed!"
    else
        log_error "❌ Health check failed!"
        return 1
    fi
}

test_api() {
    check_env_file
    
    # Read API_KEY from .env file
    API_KEY=$(grep "^API_KEY=" "$ENV_FILE" | cut -d '=' -f2)
    
    if [ -z "$API_KEY" ]; then
        log_error "API_KEY not found in $ENV_FILE"
        return 1
    fi
    
    log_info "Testing API with authentication..."
    if curl -s -f \
        -H "X-API-Key: $API_KEY" \
        -H "Content-Type: application/json" \
        -d '{"query": "test", "limit": 1}' \
        http://localhost:8080/api/search_profiles > /dev/null; then
        log_info "✅ API test passed!"
    else
        log_error "❌ API test failed!"
        return 1
    fi
}

case "${1:-start}" in
    "build")
        build_image
        ;;
    "start")
        build_image
        start_container
        sleep 3
        test_health
        ;;
    "stop")
        stop_container
        ;;
    "restart")
        stop_container
        build_image
        start_container
        sleep 3
        test_health
        ;;
    "logs")
        show_logs
        ;;
    "test")
        test_health
        test_api
        ;;
    "status")
        if docker ps -q -f name="$CONTAINER_NAME" | grep -q .; then
            log_info "✅ Container is running"
            docker ps -f name="$CONTAINER_NAME"
        else
            log_warn "❌ Container is not running"
        fi
        ;;
    *)
        echo "Usage: $0 [build|start|stop|restart|logs|test|status]"
        echo ""
        echo "Commands:"
        echo "  build   - Build the Docker image"
        echo "  start   - Build and start the container (default)"
        echo "  stop    - Stop and remove the container"
        echo "  restart - Stop, rebuild, and start the container"
        echo "  logs    - Show container logs"
        echo "  test    - Test health and API endpoints"
        echo "  status  - Check if container is running"
        echo ""
        echo "This script tests the same container configuration as ECS deployment."
        exit 1
        ;;
esac 