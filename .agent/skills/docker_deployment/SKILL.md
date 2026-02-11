---
name: Docker Deployment
description: Docker container management for TrackNet and other services
---

# Docker Deployment Skill

## Purpose
Manage Docker containers for external services like TrackNet inference server. Provides standardized deployment, health checking, and troubleshooting patterns.

## TrackNet Container

### Build and Run

**Location**: `core/trackernet/TrackNetV3/`

```bash
# Build image
cd core/trackernet/TrackNetV3
docker build -t tracknet_inference:2512 .

# Run container
docker run -d \
    --name tracknet_server \
    --gpus all \
    -p 5000:5000 \
    -v $(pwd)/weights:/app/weights \
    tracknet_inference:2512

# Check logs
docker logs tracknet_server

# Stop container
docker stop tracknet_server
docker rm tracknet_server
```

### Launch Script

**File**: `core/trackernet/tracknet.sh`

```bash
#!/bin/bash

# TrackNet Container Launch Script

CONTAINER_NAME="tracknet_server"
IMAGE_NAME="tracknet_inference:2512"
PORT=5000

# Check if container exists
if [ "$(docker ps -aq -f name=$CONTAINER_NAME)" ]; then
    echo "Stopping existing container..."
    docker stop $CONTAINER_NAME
    docker rm $CONTAINER_NAME
fi

# Check if image exists
if [ -z "$(docker images -q $IMAGE_NAME)" ]; then
    echo "Image not found. Building..."
    cd TrackNetV3
    docker build -t $IMAGE_NAME .
    cd ..
fi

# Run container
echo "Starting TrackNet server..."
docker run -d \
    --name $CONTAINER_NAME \
    --gpus all \
    -p $PORT:$PORT \
    -v $(pwd)/TrackNetV3/weights:/app/weights \
    $IMAGE_NAME

# Wait for startup
sleep 5

# Health check
if curl -s http://localhost:$PORT/health > /dev/null; then
    echo "✓ TrackNet server running on port $PORT"
else
    echo "✗ TrackNet server failed to start"
    docker logs $CONTAINER_NAME
    exit 1
fi
```

## Health Checking

### Container Health Check Script

```bash
#!/bin/bash
# .agent/skills/docker_deployment/scripts/container_health_check.sh

CONTAINER_NAME=$1
HEALTH_ENDPOINT=$2

if [ -z "$CONTAINER_NAME" ]; then
    echo "Usage: $0 <container_name> [health_endpoint]"
    exit 1
fi

# Check if container is running
if [ ! "$(docker ps -q -f name=$CONTAINER_NAME)" ]; then
    echo "✗ Container '$CONTAINER_NAME' is not running"
    
    # Check if container exists but stopped
    if [ "$(docker ps -aq -f name=$CONTAINER_NAME)" ]; then
        echo "Container exists but is stopped. Logs:"
        docker logs --tail 20 $CONTAINER_NAME
    else
        echo "Container does not exist"
    fi
    
    exit 1
fi

echo "✓ Container '$CONTAINER_NAME' is running"

# Check health endpoint if provided
if [ -n "$HEALTH_ENDPOINT" ]; then
    if curl -sf "$HEALTH_ENDPOINT" > /dev/null; then
        echo "✓ Health endpoint responsive: $HEALTH_ENDPOINT"
    else
        echo "✗ Health endpoint not responding: $HEALTH_ENDPOINT"
        exit 1
    fi
fi

# Show container stats
echo ""
echo "Container Stats:"
docker stats --no-stream $CONTAINER_NAME

exit 0
```

### Python Health Check

```python
import requests
import time
from typing import Optional

def wait_for_service(
    url: str,
    timeout: int = 30,
    interval: int = 2
) -> bool:
    """
    Wait for service to become available
    
    Args:
        url: Health check URL
        timeout: Maximum wait time in seconds
        interval: Check interval in seconds
    
    Returns:
        True if service is available, False if timeout
    """
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                print(f"✓ Service available: {url}")
                return True
        except requests.exceptions.RequestException:
            pass
        
        time.sleep(interval)
    
    print(f"✗ Service not available after {timeout}s: {url}")
    return False


# Usage
if __name__ == "__main__":
    # Wait for TrackNet
    if wait_for_service("http://localhost:5000/health"):
        print("TrackNet is ready!")
    else:
        print("TrackNet failed to start")
        exit(1)
```

## Docker Compose (Optional)

### docker-compose.yml

```yaml
version: '3.8'

services:
  tracknet:
    build:
      context: ./core/trackernet/TrackNetV3
      dockerfile: Dockerfile
    image: tracknet_inference:2512
    container_name: tracknet_server
    ports:
      - "5000:5000"
    volumes:
      - ./core/trackernet/TrackNetV3/weights:/app/weights
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 10s
      timeout: 5s
      retries: 3
    restart: unless-stopped

  backend:
    build:
      context: ./core/backend
      dockerfile: Dockerfile
    container_name: badminton_backend
    ports:
      - "8000:8000"
    environment:
      - TRACKNET_URL=http://tracknet:5000
    depends_on:
      - tracknet
    restart: unless-stopped

  frontend:
    build:
      context: ./core/birdie-buddies-frontend
      dockerfile: Dockerfile
    container_name: badminton_frontend
    ports:
      - "5173:5173"
    environment:
      - VITE_ANALYSIS_API_BASE_URL=http://localhost:8000
    depends_on:
      - backend
    restart: unless-stopped
```

### Usage

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down

# Rebuild and restart
docker-compose up -d --build
```

## Common Issues

### ❌ Docker Not Found

**Error**: `Command 'docker' not found`

**Solution**:
```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
```

### ❌ GPU Not Available in Container

**Error**: `CUDA not available in container`

**Solution**:
```bash
# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# Test GPU access
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

### ❌ Port Already in Use

**Error**: `Bind for 0.0.0.0:5000 failed: port is already allocated`

**Solution**:
```bash
# Find process using port
sudo lsof -i :5000

# Kill process
sudo kill -9 <PID>

# Or use different port
docker run -p 5001:5000 ...
```

### ❌ Container Exits Immediately

**Symptoms**: Container starts but exits right away

**Debug**:
```bash
# Check logs
docker logs <container_name>

# Run interactively
docker run -it --rm <image_name> /bin/bash

# Check exit code
docker inspect <container_name> --format='{{.State.ExitCode}}'
```

## Best Practices

1. **Use Health Checks**: Always implement health endpoints
2. **Volume Mounts**: Mount weights and data directories
3. **Resource Limits**: Set memory and CPU limits
4. **Logging**: Configure proper log drivers
5. **Restart Policies**: Use `unless-stopped` for production
6. **Network Isolation**: Use Docker networks for service communication
7. **Security**: Don't run as root inside containers

## Dockerfile Template

```dockerfile
FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# Run application
CMD ["python", "server.py"]
```

## Related Files

- TrackNet Dockerfile: `core/trackernet/TrackNetV3/Dockerfile`
- Launch script: `core/trackernet/tracknet.sh`
- Health check: `.agent/skills/docker_deployment/scripts/container_health_check.sh`

## Quick Reference

```bash
# Build and run
docker build -t my_image .
docker run -d --name my_container -p 5000:5000 my_image

# Manage containers
docker ps                    # List running
docker ps -a                 # List all
docker logs my_container     # View logs
docker exec -it my_container /bin/bash  # Shell access
docker stop my_container     # Stop
docker rm my_container       # Remove

# Cleanup
docker system prune -a       # Remove unused images/containers
```
