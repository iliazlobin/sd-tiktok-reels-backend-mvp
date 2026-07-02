# TikTok/Reels MVP

A short-form video backend (TikTok/Reels-style) implementing the core upload → feed → engage loop.

## Stack

| Layer | Technology |
|-------|-----------|
| API    | FastAPI (Python 3.12) |
| Database | PostgreSQL 16 (async via asyncpg) |
| Cache | Redis 7 (feed sorted sets, engagement counters) |
| Migrations | Alembic |
| Container | Docker Compose |

## Quick Start

```bash
# Start the full stack
docker compose up --build -d

# Run migrations
docker compose exec app alembic upgrade head

# Check the service is alive
curl http://localhost:8010/healthz
# → {"status":"ok"}
```

The host port defaults to `8010`. Override it:

```bash
APP_PORT=8020 docker compose up -d
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/healthz` | Health check |
| `POST` | `/api/v1/users` | Create user |
| `GET` | `/api/v1/users/{id}` | Get user profile |
| `GET` | `/api/v1/users/{id}/videos` | Creator video catalog |
| `POST` | `/api/v1/users/{id}/follow` | Follow a user |
| `DELETE` | `/api/v1/users/{id}/follow` | Unfollow a user |
| `POST` | `/api/v1/videos` | Publish a video |
| `GET` | `/api/v1/videos/{id}` | Video detail |
| `POST` | `/api/v1/videos/{id}/segments` | Add video segments |
| `GET` | `/api/v1/feed` | Trending feed |
| `GET` | `/api/v1/videos/{id}/manifest` | DASH manifest |
| `GET` | `/api/v1/segments/{id}` | Video segment bytes |
| `POST` | `/api/v1/videos/{id}/like` | Like a video |
| `DELETE` | `/api/v1/videos/{id}/like` | Unlike a video |
| `POST` | `/api/v1/videos/{id}/comments` | Post a comment |
| `GET` | `/api/v1/videos/{id}/comments` | List comments |
| `GET` | `/api/v1/search` | Search videos/hashtags/users |

## Architecture

FastAPI app factory with three clean layers: **routers** (HTTP → service call), **services** (business logic + data access), and **models/schemas** (ORM + DTOs). PostgreSQL stores all authoritative state; Redis caches the trending feed as sorted sets and denormalized engagement counters.

See [design.md](design.md) for the full architecture and data model.

## Development

```bash
# Install with dev extras
pip install -e ".[dev]"

# Run tests
pytest tests/

# Lint
ruff check src/
```
