---
name: docker-patterns
description: Use when setting up Docker for local development, writing Dockerfiles, configuring Docker Compose, or troubleshooting container issues
---
## Docker Patterns

### Dockerfile Best Practices

#### Multi-Stage Build
```dockerfile
# Build stage
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Production stage
FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY . .
CMD ["gunicorn", "-c", "gunicorn.conf.py", "api.main:app"]
```

#### Security
- Never run as root: `RUN useradd -m appuser && USER appuser`
- Don't copy .env or secrets
- Use `.dockerignore` to exclude .git, __pycache__, .venv, .env
- Pin base image versions: `python:3.12-slim` not `python:latest`

### Docker Compose for Local Dev

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - .:/app
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy

  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: test
      POSTGRES_PASSWORD: test
      POSTGRES_DB: test
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U test"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  pgdata:
```

### .dockerignore
```
.git
.venv
__pycache__
*.pyc
.env
.env.*
node_modules
.htmlcov/
.pytest_cache/
.ruff_cache/
```

### Common Issues
- **Permission denied on volumes**: Ensure UID/GID match between container and host
- **Stale images**: `docker compose build --no-cache`
- **Orphan containers**: `docker compose down -v` (removes volumes too)
- **Port conflicts**: Check with `docker ps` before starting
