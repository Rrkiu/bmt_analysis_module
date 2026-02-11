#!/bin/bash

# ==========================================
# Container Health Check Script
# ==========================================

CONTAINER_NAME=$1
HEALTH_ENDPOINT=$2

if [ -z "$CONTAINER_NAME" ]; then
    echo "Usage: $0 <container_name> [health_endpoint]"
    echo ""
    echo "Examples:"
    echo "  $0 tracknet_server"
    echo "  $0 tracknet_server http://localhost:5000/health"
    exit 1
fi

echo "=========================================="
echo "Container Health Check: $CONTAINER_NAME"
echo "=========================================="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "✗ Docker is not running"
    exit 1
fi

echo "✓ Docker is running"

# Check if container exists
if [ ! "$(docker ps -aq -f name=^${CONTAINER_NAME}$)" ]; then
    echo "✗ Container '$CONTAINER_NAME' does not exist"
    exit 1
fi

# Check if container is running
if [ ! "$(docker ps -q -f name=^${CONTAINER_NAME}$)" ]; then
    echo "✗ Container '$CONTAINER_NAME' exists but is not running"
    echo ""
    echo "Container status:"
    docker ps -a -f name=^${CONTAINER_NAME}$
    echo ""
    echo "Last 20 log lines:"
    docker logs --tail 20 $CONTAINER_NAME
    exit 1
fi

echo "✓ Container is running"

# Get container info
CONTAINER_ID=$(docker ps -q -f name=^${CONTAINER_NAME}$)
CONTAINER_STATUS=$(docker inspect --format='{{.State.Status}}' $CONTAINER_ID)
CONTAINER_UPTIME=$(docker inspect --format='{{.State.StartedAt}}' $CONTAINER_ID)

echo ""
echo "Container Info:"
echo "  ID: $CONTAINER_ID"
echo "  Status: $CONTAINER_STATUS"
echo "  Started: $CONTAINER_UPTIME"

# Check health endpoint if provided
if [ -n "$HEALTH_ENDPOINT" ]; then
    echo ""
    echo "Checking health endpoint: $HEALTH_ENDPOINT"
    
    if curl -sf "$HEALTH_ENDPOINT" > /dev/null 2>&1; then
        echo "✓ Health endpoint is responsive"
        
        # Show response
        RESPONSE=$(curl -s "$HEALTH_ENDPOINT")
        echo "  Response: $RESPONSE"
    else
        echo "✗ Health endpoint is not responding"
        exit 1
    fi
fi

# Show resource usage
echo ""
echo "Resource Usage:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}" $CONTAINER_NAME

# Show port mappings
echo ""
echo "Port Mappings:"
docker port $CONTAINER_NAME

echo ""
echo "=========================================="
echo "✓ Health check passed"
echo "=========================================="

exit 0
