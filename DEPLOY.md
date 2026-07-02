# Deploy — TikTok/Reels MVP

## Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- Port 8010 free on the host (override via `APP_PORT`)

## First Run

```bash
# 1. Start all services (builds the app image, starts Postgres + Redis)
docker compose up --build -d

# 2. Wait for health checks to pass (30–60 seconds)
docker compose ps

# 3. Run database migrations
docker compose exec app alembic upgrade head

# 4. Verify the app is alive
curl http://localhost:8010/healthz
# → {"status":"ok"}
```

## Daily Use

```bash
# Start (fast — image already built)
docker compose up -d

# View logs
docker compose logs -f app

# Stop (keeps volumes)
docker compose down

# Full reset (destroys volumes, seeds, everything)
docker compose down --volumes
```

## Configuration

All configuration is via environment variables (set in `.env` or passed to `docker compose`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://tiktok:tiktok@db:5432/tiktok_reels` | Postgres connection string |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string |
| `APP_PORT` | `8010` | Host port mapped to the container's port 8000 |

In Docker Compose mode, `DATABASE_URL` and `REDIS_URL` are set by `docker-compose.yml` and typically don't need `.env` overrides. Set `APP_PORT` to avoid port collisions.

## Port Collisions

If port 8010 is already in use, pick a free port:

```bash
APP_PORT=8020 docker compose up -d
```

The `docker-compose.yml` publishes only the app port. Backing services (Postgres, Redis) are internal to the compose network and never published — they won't collide with any services already running on the host.

## Running Tests

```bash
# Unit/integration tests (no Docker needed)
pip install -e ".[dev]"
pytest tests/

# Acceptance tests (against a running stack)
API_BASE_URL="http://localhost:8010" pip install httpx pytest
API_BASE_URL="http://localhost:8010" python -m pytest verify/acceptance/ -q
```
