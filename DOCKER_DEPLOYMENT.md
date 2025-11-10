# Docker Deployment Guide

This guide explains how to deploy TranslateBookWithLLM using Docker.

## Prerequisites

- Docker installed (version 20.10 or higher)
- Docker Compose installed (version 1.29 or higher)
- For Ollama: Ollama running on your host machine with models installed

## Quick Start

### 1. Create Environment File

Copy the example environment file and configure it:

```bash
cp .env.docker.example .env
```

Edit `.env` with your settings (see Configuration section below).

### 2. Build and Run

```bash
# Build and start the container
docker-compose up -d

# View logs
docker-compose logs -f

# Check container health
docker-compose ps
```

### 3. Access the Application

Open your browser to: `http://localhost:5000`

## Configuration

### Using Ollama (Local LLM)

**Windows/Mac:**

Edit your `.env` file:

```env
LLM_PROVIDER=ollama
API_ENDPOINT=http://host.docker.internal:11434/api/generate
DEFAULT_MODEL=mistral-small:24b
```

**Linux:**

Option 1: Use host IP address

```env
LLM_PROVIDER=ollama
API_ENDPOINT=http://192.168.1.100:11434/api/generate  # Replace with your host IP
DEFAULT_MODEL=mistral-small:24b
```

Option 2: Uncomment `extra_hosts` in [docker-compose.yml](docker-compose.yml:64-66):

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

Then use:

```env
API_ENDPOINT=http://host.docker.internal:11434/api/generate
```

### Using Gemini (Cloud LLM)

Edit your `.env` file:

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.0-flash
```

### Using OpenAI (Cloud LLM)

Edit your `.env` file:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=your_api_key_here
```

## Advanced Configuration

### Custom Port

To run on a different port (e.g., 8080):

```env
PORT=8080
```

Then update the port mapping in your browser: `http://localhost:8080`

### Persistent Data

The Docker setup automatically creates persistent volumes:

- `./translated_files` - Translated output files
- `./logs` - Application logs (if logging is configured)

These folders are created automatically and persist between container restarts.

### Resource Limits

To add memory/CPU limits, edit [docker-compose.yml](docker-compose.yml):

```yaml
services:
  translatebook:
    # ... other settings ...
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          memory: 2G
```

## Common Commands

### Start/Stop

```bash
# Start container
docker-compose up -d

# Stop container
docker-compose down

# Restart container
docker-compose restart
```

### View Logs

```bash
# Follow logs in real-time
docker-compose logs -f

# View last 100 lines
docker-compose logs --tail=100

# View logs for specific service
docker-compose logs translatebook
```

### Rebuild After Code Changes

```bash
# Rebuild and restart
docker-compose up -d --build

# Force complete rebuild
docker-compose build --no-cache
docker-compose up -d
```

### Access Container Shell

```bash
# Open bash shell inside container
docker-compose exec translatebook bash

# Run Python commands
docker-compose exec translatebook python translate.py --help
```

## Health Monitoring

The container includes a health check that verifies the API is responding:

```bash
# Check health status
docker-compose ps

# View detailed health status
docker inspect --format='{{json .State.Health}}' translatebook-llm | python -m json.tool
```

Health check endpoint: `http://localhost:5000/api/health`

## Troubleshooting

### Container Won't Start

**Check logs:**

```bash
docker-compose logs
```

**Common issues:**

1. **Port already in use:**
   ```
   Error: bind: address already in use
   ```
   Solution: Change `PORT` in `.env` or stop the conflicting service

2. **Environment variables not loaded:**
   - Ensure `.env` file exists in same directory as `docker-compose.yml`
   - Check file permissions: `chmod 644 .env`

### Cannot Connect to Ollama

**Symptoms:**

```
Connection refused to localhost:11434
```

**Solutions:**

1. **Windows/Mac:** Verify `API_ENDPOINT` uses `host.docker.internal`:
   ```env
   API_ENDPOINT=http://host.docker.internal:11434/api/generate
   ```

2. **Linux:** Use host IP or enable `extra_hosts` in docker-compose.yml

3. **Verify Ollama is running:**
   ```bash
   curl http://localhost:11434/api/tags
   ```

4. **Check Ollama binding:**
   Ensure Ollama listens on all interfaces, not just localhost.

   Set environment variable:
   ```bash
   export OLLAMA_HOST=0.0.0.0:11434
   ```

### Translation Fails

**Check model availability:**

```bash
# List available models in Ollama
curl http://localhost:11434/api/tags

# Pull a model if needed
docker-compose exec translatebook curl -X POST http://host.docker.internal:11434/api/pull \
  -d '{"name": "mistral-small:24b"}'
```

**Verify configuration:**

```bash
# Check environment variables inside container
docker-compose exec translatebook env | grep -E "LLM_PROVIDER|API_ENDPOINT|DEFAULT_MODEL"
```

### Health Check Failing

**View health check logs:**

```bash
docker inspect translatebook-llm | grep -A 10 Health
```

**Test health endpoint manually:**

```bash
docker-compose exec translatebook curl http://localhost:5000/api/health
```

### File Permissions (Linux)

If you encounter permission errors with translated files:

```bash
# Set correct ownership
sudo chown -R $USER:$USER ./translated_files

# Or run with user mapping
docker-compose exec -u $(id -u):$(id -g) translatebook bash
```

## Production Deployment

### Using Environment Variables Directly

Instead of `.env` file, pass variables directly:

```bash
docker-compose up -d \
  -e LLM_PROVIDER=gemini \
  -e GEMINI_API_KEY=your_key \
  -e PORT=8080
```

### Behind a Reverse Proxy

Example nginx configuration:

```nginx
server {
    listen 80;
    server_name translate.example.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Docker Swarm / Kubernetes

For orchestration, consider:

1. **Using secrets** for API keys
2. **External volumes** for translated files
3. **Load balancing** for multiple replicas
4. **Resource limits** per container

## Security Considerations

1. **Never commit `.env` file** - It contains sensitive API keys
2. **Use secrets management** in production (Docker secrets, Kubernetes secrets)
3. **Limit container permissions** - Run as non-root user if possible
4. **Network isolation** - Use Docker networks to isolate services
5. **Regular updates** - Keep base images and dependencies updated

## Performance Optimization

### Increase Context Window

For larger chunks and better translations:

```env
OLLAMA_NUM_CTX=16384
MAIN_LINES_PER_CHUNK=50
```

### Adjust Timeouts

For slower models or large files:

```env
REQUEST_TIMEOUT=1800  # 30 minutes
```

### Enable Auto-adjustment

Let the system optimize chunk sizes:

```env
AUTO_ADJUST_CONTEXT=true
MIN_CHUNK_SIZE=5
MAX_CHUNK_SIZE=100
```

## Cleanup

### Remove Container and Volumes

```bash
# Stop and remove container
docker-compose down

# Remove volumes (WARNING: deletes translated files)
docker-compose down -v

# Remove images
docker rmi translatebookwithllm_translatebook
```

### Clean Up Old Images

```bash
# Remove dangling images
docker image prune

# Remove all unused images
docker image prune -a
```

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Project README](README.md)
- [CLAUDE.md](CLAUDE.md) - Architecture and development guide
- [SIMPLE_MODE_README.md](SIMPLE_MODE_README.md) - EPUB Simple Mode guide
