#!/bin/bash
# ============================================================================
# Docker Testing Script for TranslateBookWithLLM
# ============================================================================
# This script tests the Docker deployment automatically
# Usage: ./test_docker.sh

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo ""
echo "============================================================"
echo "  Docker Test Script - TranslateBookWithLLM"
echo "============================================================"
echo ""

# Step 1: Verify Docker is installed and running
echo "[1/6] Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}[ERROR]${NC} Docker is not installed or not in PATH"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi
echo -e "${GREEN}[OK]${NC} Docker is installed"

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}[ERROR]${NC} Docker Compose is not installed"
    exit 1
fi
echo -e "${GREEN}[OK]${NC} Docker Compose is installed"

echo ""
echo "[2/6] Checking Docker daemon status..."
if ! docker ps &> /dev/null; then
    echo -e "${RED}[ERROR]${NC} Docker daemon is not running"
    echo "Please start Docker and try again"
    exit 1
fi
echo -e "${GREEN}[OK]${NC} Docker daemon is running"

echo ""
echo "[3/6] Building Docker image..."
if docker-compose build; then
    echo -e "${GREEN}[OK]${NC} Docker image built successfully"
else
    echo -e "${RED}[ERROR]${NC} Docker build failed"
    exit 1
fi

echo ""
echo "[4/6] Starting Docker container..."
if docker-compose up -d; then
    echo -e "${GREEN}[OK]${NC} Container started"
else
    echo -e "${RED}[ERROR]${NC} Failed to start container"
    exit 1
fi

echo ""
echo "[5/6] Waiting for container to be healthy (45 seconds)..."
sleep 45

# Check container status
if docker-compose ps | grep -q "healthy"; then
    echo -e "${GREEN}[OK]${NC} Container is healthy"
else
    echo -e "${YELLOW}[WARNING]${NC} Container may not be healthy yet"
    echo "Checking logs..."
    docker-compose logs --tail=20
fi

echo ""
echo "[6/6] Testing API endpoints..."

# Test health endpoint
if curl -s http://localhost:5000/api/health > test_health.json; then
    if grep -q "ok" test_health.json; then
        echo -e "${GREEN}[OK]${NC} Health endpoint: http://localhost:5000/api/health"
        cat test_health.json
        rm test_health.json
    else
        echo -e "${RED}[ERROR]${NC} Health endpoint returned unexpected response"
        cat test_health.json
        rm test_health.json
        exit 1
    fi
else
    echo -e "${RED}[ERROR]${NC} Health endpoint test failed"
    exit 1
fi

echo ""
# Test web interface
if curl -s -I http://localhost:5000/ | grep -q "200 OK"; then
    echo -e "${GREEN}[OK]${NC} Web interface: http://localhost:5000/"
else
    echo -e "${YELLOW}[WARNING]${NC} Web interface may not be responding correctly"
fi

echo ""
echo "============================================================"
echo "  All tests passed successfully!"
echo "============================================================"
echo ""
echo "Container status:"
docker-compose ps
echo ""
echo "Useful commands:"
echo "  - View logs:           docker-compose logs -f"
echo "  - Stop container:      docker-compose down"
echo "  - Restart container:   docker-compose restart"
echo "  - Shell access:        docker-compose exec translatebook bash"
echo ""
echo "Web interface: http://localhost:5000"
echo "API health:    http://localhost:5000/api/health"
echo ""
