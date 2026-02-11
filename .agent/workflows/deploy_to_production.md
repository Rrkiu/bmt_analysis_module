---
description: Deploy application to production environment
---

# Deploy to Production Workflow

This workflow guides you through deploying the badminton analysis system to a production environment.

## Prerequisites

- Production server with Docker and Docker Compose
- GPU support (NVIDIA drivers + nvidia-docker)
- Domain name configured (optional)
- SSL certificates (for HTTPS)

## Steps

### 1. Prepare Production Environment

**On production server**:

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install NVIDIA Container Toolkit (for GPU)
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -s -L https://nvidia.github.io/nvidia-docker/gpgkey | sudo apt-key add -
curl -s -L https://nvidia.github.io/nvidia-docker/$distribution/nvidia-docker.list | \
    sudo tee /etc/apt/sources.list.d/nvidia-docker.list

sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo systemctl restart docker

# Verify GPU access
docker run --rm --gpus all nvidia/cuda:11.0-base nvidia-smi
```

### 2. Clone Repository

```bash
# Clone to production server
git clone https://github.com/your-repo/bmt_demo.git
cd bmt_demo
```

### 3. Configure Environment Variables

**Create production .env files**:

**Backend** (`core/backend/.env.production`):
```bash
# API Settings
API_PREFIX=/api
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com

# File Upload
MAX_UPLOAD_SIZE=52428800  # 50MB

# TrackNet (if using)
TRACKNET_URL=http://tracknet:5000

# Logging
LOG_LEVEL=INFO
```

**Frontend** (`core/birdie-buddies-frontend/.env.production`):
```bash
VITE_ANALYSIS_API_BASE_URL=https://api.yourdomain.com
```

### 4. Build Production Images

**Option A: Using Docker Compose**

Create `docker-compose.prod.yml`:

```yaml
version: '3.8'

services:
  backend:
    build:
      context: ./core/backend
      dockerfile: Dockerfile.prod
    image: badminton-backend:latest
    container_name: badminton_backend
    ports:
      - "8000:8000"
    environment:
      - ENV=production
    env_file:
      - ./core/backend/.env.production
    volumes:
      - ./storage:/app/storage
      - ./core/backend/modules:/app/modules
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: always

  frontend:
    build:
      context: ./core/birdie-buddies-frontend
      dockerfile: Dockerfile.prod
      args:
        - VITE_ANALYSIS_API_BASE_URL=https://api.yourdomain.com
    image: badminton-frontend:latest
    container_name: badminton_frontend
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/ssl:/etc/nginx/ssl
    restart: always

  tracknet:
    build:
      context: ./core/trackernet/TrackNetV3
    image: tracknet_inference:latest
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
    restart: always
```

**Build images**:
```bash
docker-compose -f docker-compose.prod.yml build
```

**Option B: Manual Build**

```bash
# Build backend
cd core/backend
docker build -t badminton-backend:latest -f Dockerfile.prod .

# Build frontend
cd ../birdie-buddies-frontend
docker build -t badminton-frontend:latest -f Dockerfile.prod .

# Build TrackNet
cd ../trackernet/TrackNetV3
docker build -t tracknet_inference:latest .
```

### 5. Setup Nginx (Reverse Proxy)

**Create** `nginx/nginx.conf`:

```nginx
upstream backend {
    server backend:8000;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    
    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    # SSL Configuration
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Frontend
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # File upload size
        client_max_body_size 50M;
    }
}
```

### 6. Deploy Application

```bash
# Start all services
docker-compose -f docker-compose.prod.yml up -d

# Check logs
docker-compose -f docker-compose.prod.yml logs -f

# Verify all containers running
docker ps
```

### 7. Health Checks

**Check each service**:

```bash
# Backend
curl https://api.yourdomain.com/api/health

# TrackNet (if using)
curl http://localhost:5000/health

# Frontend
curl https://yourdomain.com
```

**Use health check script**:
```bash
sh .agent/skills/docker_deployment/scripts/container_health_check.sh badminton_backend
sh .agent/skills/docker_deployment/scripts/container_health_check.sh tracknet_server
```

### 8. Setup Monitoring (Optional)

**Install monitoring tools**:

```bash
# Prometheus + Grafana
docker-compose -f docker-compose.monitoring.yml up -d
```

**Monitor logs**:
```bash
# Real-time logs
docker-compose -f docker-compose.prod.yml logs -f backend

# Save logs to file
docker-compose -f docker-compose.prod.yml logs backend > backend.log
```

### 9. Setup Backup

**Create backup script** (`scripts/backup.sh`):

```bash
#!/bin/bash

BACKUP_DIR="/backups/bmt_demo"
DATE=$(date +%Y%m%d_%H%M%S)

# Backup storage directory
tar -czf $BACKUP_DIR/storage_$DATE.tar.gz ./storage

# Backup database (if applicable)
# docker exec postgres pg_dump -U user db > $BACKUP_DIR/db_$DATE.sql

# Keep only last 7 days
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete

echo "Backup completed: $DATE"
```

**Setup cron job**:
```bash
# Run daily at 2 AM
0 2 * * * /path/to/scripts/backup.sh
```

### 10. Configure Firewall

```bash
# Allow HTTP/HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow SSH
sudo ufw allow 22/tcp

# Enable firewall
sudo ufw enable
```

## Post-Deployment

### Verify Deployment

- [ ] Frontend accessible at https://yourdomain.com
- [ ] API responding at https://api.yourdomain.com/api/health
- [ ] SSL certificate valid
- [ ] All containers running
- [ ] GPU accessible in containers
- [ ] File uploads working
- [ ] Video analysis functional

### Update Deployment

**To update code**:

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d

# Check logs for errors
docker-compose -f docker-compose.prod.yml logs -f
```

### Rollback

**If deployment fails**:

```bash
# Stop current deployment
docker-compose -f docker-compose.prod.yml down

# Checkout previous version
git checkout <previous-commit>

# Rebuild and restart
docker-compose -f docker-compose.prod.yml build
docker-compose -f docker-compose.prod.yml up -d
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs <container_name>

# Check resource usage
docker stats

# Restart container
docker restart <container_name>
```

### SSL Certificate Issues

```bash
# Verify certificate files
ls -la nginx/ssl/

# Test SSL configuration
docker exec badminton_frontend nginx -t

# Reload nginx
docker exec badminton_frontend nginx -s reload
```

### Performance Issues

```bash
# Check GPU usage
nvidia-smi

# Check container resources
docker stats

# Scale services (if using docker-compose)
docker-compose -f docker-compose.prod.yml up -d --scale backend=2
```

## Related Skills

- Docker Deployment: `.agent/skills/docker_deployment/SKILL.md`
- API Integration: `.agent/skills/api_integration/SKILL.md`
