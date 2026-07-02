# Deploy — TikTok/Reels MVP

Slug: `tiktok-reels`

## Prerequisites

- Docker Engine 24+ with Compose plugin (`docker compose version`)
- curl (for healthcheck probes)
- A running Docker daemon
- Port 8010 free on the host (overridable via `APP_PORT`)

## Quick Start — From Clean Checkout to Running

```bash
# 1. Clone / cd into the project
cd /path/to/tiktok-reels

# 2. Copy the env template (optional — built-in defaults work)
cp .env.example .env

# 3. Build and start the full stack (app + postgres + redis)
#    APP_PORT controls the host-side port; in-container port is always 8000.
APP_PORT=8010 docker compose up --build -d

# 4. Wait for startup (health checks auto-sequence: postgres → redis → app)
sleep 15

# 5. Verify the stack is healthy
curl -sf http://localhost:8010/healthz
# → {"status":"ok"}

# 6. Run database migrations
docker compose exec app alembic upgrade head

# 7. Quick functional smoke test — create a user and a video
curl -sf http://localhost:8010/api/v1/users \
  -H 'Content-Type: application/json' \
  -d '{"username": "smoke_test"}'
# → {"user_id":"...","username":"smoke_test"}

# Grab the user_id from the response and create a video:
curl -sf http://localhost:8010/api/v1/videos \
  -H 'Content-Type: application/json' \
  -d '{"author_id":"<user_id>","caption":"first reels video","duration_ms":15000}'
# → {"video_id":"...","caption":"first reels video",...}

# Check the trending feed:
curl -sf http://localhost:8010/api/v1/feed
# → {"videos":[...],"next_cursor":null}
```

> Note: The `lifespan` handler in `main.py` auto-creates tables on startup via `Base.metadata.create_all()`, so in many cases migrations aren't strictly needed. The alembic path is still available for schema versioning.

## Port Configuration

| Variable   | Default | Description                                    |
|-----------|---------|------------------------------------------------|
| `APP_PORT` | `8010`  | Host-side port mapped to in-container `8000`   |

```bash
# Run on a different port
APP_PORT=8020 docker compose up -d
```

## Environment

The app is configured entirely through environment variables:

```bash
cp .env.example .env
# Edit .env to override defaults — the example has all variable names
```

The `docker-compose.yml`'s `environment:` block sets the critical values
(`DATABASE_URL`, `REDIS_URL`). The `.env` file augments these with optional
settings.

Secrets (`DATABASE_URL` credentials) belong in `.env` — never committed to the repo.

## Health Checks

Every service has a Docker HEALTHCHECK. Compose dependency waits ensure
the stack doesn't start serving before PostgreSQL and Redis are ready.

| Service | Healthcheck command                                              | Interval |
|---------|------------------------------------------------------------------|----------|
| db      | `pg_isready -U tiktok`                                           | 5s       |
| redis   | `redis-cli ping`                                                 | 5s       |
| app     | `python -c "import urllib.request; ..." http://localhost:8000/healthz` | 10s      |

To manually probe:

```bash
docker inspect --format='{{.State.Health.Status}}' tiktok-reels-db
docker inspect --format='{{.State.Health.Status}}' tiktok-reels-redis
docker inspect --format='{{.State.Health.Status}}' tiktok-reels-app
```

The health endpoint returns `{"status":"ok"}` when the app is reachable.

## Logs

```bash
# Follow app logs
docker compose logs -f app

# Tail recent logs
docker compose logs app --tail=100
docker compose logs db --tail=50
docker compose logs redis --tail=50
```

## Testing

```bash
# White-box unit tests (requires a running Postgres — use compose stack,
# or run locally with SQLite via the dev extras)
docker compose exec app python -m pytest tests/ -v
# → 40 passed

# Lint (ruff)
pip install ruff==0.15.20
ruff check src/ tests/ verify/
ruff format --check src/ tests/ verify/

# Black-box acceptance tests (requires running stack on APP_PORT)
API_BASE_URL="http://localhost:8010" python -m pytest verify/acceptance -v
```

## CI/CD

Three GitHub Actions workflows live in `.github/workflows/`:

| Workflow         | Trigger             | What it does                                              |
|-----------------|---------------------|-----------------------------------------------------------|
| `lint.yml`      | PR + push to `main` | `ruff check` + `ruff format --check`                      |
| `ci.yml`        | PR + push to `main` | Install deps, run unit tests, build Docker image          |
| `functional.yml` | PR + push to `main` | `docker compose up`, run acceptance tests, `docker compose down` |

All three must pass before a PR can merge.

## Stop & Cleanup

```bash
# Stop containers (keeps volumes — Postgres data persists)
docker compose down

# Full teardown (wipes all data)
docker compose down --volumes --remove-orphans
```

## Production Notes

- Use a managed Postgres instance with automated backups.
- Pin Redis persistence (AOF + RDB) for cache durability if feed state must survive restarts.
- Rate-limit video upload endpoints to prevent abuse.
- The `pgdata` volume stores all database state — back it up regularly.
