# TikTok/Reels MVP

[![lint](https://github.com/iliazlobin/sd-tiktok-reels-backend-mvp/actions/workflows/lint.yml/badge.svg)](https://github.com/iliazlobin/sd-tiktok-reels-backend-mvp/actions/workflows/lint.yml)
[![ci](https://github.com/iliazlobin/sd-tiktok-reels-backend-mvp/actions/workflows/ci.yml/badge.svg)](https://github.com/iliazlobin/sd-tiktok-reels-backend-mvp/actions/workflows/ci.yml)
[![functional](https://github.com/iliazlobin/sd-tiktok-reels-backend-mvp/actions/workflows/functional.yml/badge.svg)](https://github.com/iliazlobin/sd-tiktok-reels-backend-mvp/actions/workflows/functional.yml)

A short-form video backend (TikTok/Reels-style) implementing the core upload → feed → engage → search loop. One FastAPI process backed by PostgreSQL 16 for authoritative state and Redis 7 for feed caching and engagement counters.

**Slug:** `tiktok-reels`  
**Version:** `0.1.0`  
**Python:** `>=3.11`

---

## Quick Start

```bash
# 1. Start the full stack
docker compose up --build -d

# 2. Run database migrations
docker compose exec app alembic upgrade head

# 3. Check the service is alive
curl http://localhost:8010/healthz
# → {"status":"ok"}
```

The host port defaults to `8010`. Override it:

```bash
APP_PORT=8020 docker compose up -d
```

**Prerequisites:** Docker Compose v2, `APP_PORT` env not required (defaults to 8010).

---

## Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| API | FastAPI (Python 3.12-slim) | REST endpoints, Pydantic validation |
| Database | PostgreSQL 16 (async via asyncpg) | Users, videos, hashtags, comments, likes, follows, segments |
| Cache | Redis 7 (redis-py async) | Feed sorted sets (`feed:global`), engagement counters (`counters:{video_id}`) |
| Migrations | Alembic | Schema versioning |
| Container | Docker Compose | `db` + `redis` + `app` with healthchecks and named network |

---

## API Reference

### Health

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/healthz` | Liveness check → `200 {"status": "ok"}` |

### Users

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/users` | Create user — `201` with profile. `409` on duplicate username. |
| `GET` | `/api/v1/users/{user_id}` | Get user profile with follower/following counts — `404` if not found. |
| `GET` | `/api/v1/users/{user_id}/videos` | Creator's video catalog, reverse-chronological, cursor-paginated. |
| `POST` | `/api/v1/users/{followee_id}/follow` | Follow a creator. Idempotent. `422` on self-follow. |
| `DELETE` | `/api/v1/users/{followee_id}/follow` | Unfollow a creator. Idempotent. |

### Videos

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/videos` | Publish a video — `201` with metadata, hashtag upsert. `404` on unknown author. |
| `GET` | `/api/v1/videos/{video_id}` | Video detail with author, hashtags, engagement counts — `404` if not found. |
| `POST` | `/api/v1/videos/{video_id}/segments` | Add video quality segments in bulk for ABR playback. |

### Feed

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/feed` | Trending feed, recency-biased, cursor-paginated (15/page). |

### Streaming

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/videos/{video_id}/manifest` | MPEG-DASH MPD manifest with quality levels — `404` if no segments. |
| `GET` | `/api/v1/segments/{segment_id}` | Raw mock `.ts` segment bytes — `404` if not found. |

### Engagement

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/videos/{video_id}/like` | Like a video. Idempotent. |
| `DELETE` | `/api/v1/videos/{video_id}/like` | Unlike a video. Idempotent. |
| `POST` | `/api/v1/videos/{video_id}/comments` | Post a comment — `201`. `404` on unknown video/user. |
| `GET` | `/api/v1/videos/{video_id}/comments` | List comments, oldest-first, cursor-paginated (20/page). |

### Search

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/search` | Full-text search across videos, hashtags, and usernames. `?q=` query, `?type=all|video|hashtag|user`. |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     FastAPI App                         │
│                                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │  Users   │ │  Videos  │ │  Feed    │ │ Streaming │  │
│  │  Router  │ │  Router  │ │  Router  │ │  Router   │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬─────┘  │
│  ┌────┴─────┐ ┌────┴─────┐ ┌────┴─────┐ ┌──────┴────┐ │
│  │  User    │ │  Video   │ │  Feed    │ │ Streaming │  │
│  │  Service │ │  Service │ │  Service │ │  Service  │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────┬────┘  │
│  ┌────┴─────┐ ┌────┴─────┐ ┌────┴─────┐ ┌──────┴────┐ │
│  │ Comment  │ │Engagement│ │  Search  │ │           │  │
│  │ Service  │ │ Service  │ │  Service │ │           │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └───────────┘  │
└───────┼────────────┼────────────┼───────────────────────┘
        │            │            │
   ┌────▼────────────▼────────────▼───────────────────┐
   │           PostgreSQL 16                           │
   │  users, videos, hashtags, video_hashtags,         │
   │  comments, likes, follows, video_segments         │
   │  + GIN FTS indexes on caption + hashtag name      │
   └────────────────────┬──────────────────────────────┘
                        │
   ┌────────────────────▼──────────────────────────────┐
   │           Redis 7                                  │
   │  feed:global (sorted set, top-100 scored videos)   │
   │  counters:{video_id} (denormalized like counts)   │
   └───────────────────────────────────────────────────┘
```

**Key design principle:** Routers parse HTTP and validate with Pydantic schemas, then delegate to services. Services own all domain logic and data access. No business logic lives in routers.

---

## Project Layout

```
src/tiktok_reels/
├── main.py          # App factory, lifespan (auto-create tables), /healthz
├── config.py        # Settings via pydantic-settings (env-driven)
├── database.py      # Async SQLAlchemy engine + session factory
├── redis.py         # Redis async client factory
├── models/          # SQLAlchemy ORM models
│   ├── user.py      # User
│   ├── video.py     # Video (fts tsvector generated column)
│   ├── hashtag.py   # Hashtag + VideoHashtag junction
│   ├── comment.py   # Comment
│   ├── engagement.py # Like + Follow (both with UNIQUE constraints)
│   └── segment.py   # VideoSegment (ABR quality tiers)
├── schemas/         # Pydantic request/response models
│   ├── user.py, video.py, feed.py, comment.py
│   ├── engagement.py, search.py
│   └── common.py    # PaginatedResponse, cursor encode/decode helpers
├── routers/         # FastAPI route handlers (thin, delegate to services)
│   ├── users.py, videos.py, feed.py, streaming.py
│   ├── comments.py, engagement.py, search.py
│   └── health.py
└── services/        # Business logic layer
    ├── user_service.py, video_service.py, feed_service.py
    ├── streaming_service.py, comment_service.py
    ├── engagement_service.py, search_service.py

tests/               # White-box unit/integration tests (SQLite)
└── test_*.py

verify/acceptance/   # Black-box acceptance tests (httpx + running compose stack)
├── conftest.py      # Fixtures, helpers: create_user, create_video, get_feed, etc.
├── test_healthz.py
├── test_fr1_upload_video.py
├── test_fr2_feed.py
├── test_fr3_playback.py
├── test_fr4_engagement.py
├── test_fr5_social.py
└── test_fr6_search.py
```

---

## Test Suite

### Unit / Integration Tests (40 tests — SQLite-backed, no external deps)

| File | Tests | What it covers |
|------|-------|---------------|
| `tests/test_common.py` | 6 | Cursor token encode/decode, base64 format, malformed input handling |
| `tests/test_user_service.py` | 12 | User CRUD, follow/unfollow idempotency, follower/following counter updates, creator catalog cursor pagination |
| `tests/test_comment_service.py` | 6 | Comment create, unknown video/user errors, comment listing with cursor pagination |
| `tests/test_video_service.py` | 7 | Video creation with/without hashtags, hashtag deduplication, unknown author error, segment bulk insert |
| `tests/test_streaming_service.py` | 2 | MPD manifest XML generation (2 quality tiers, 3 segment URLs), empty segments edge case |
| `tests/test_engagement_service.py` | 6 | Like/unlike idempotency, counter accuracy, unknown video/user errors |

### Acceptance Tests (black-box — require running compose stack)

| File | FR | What it asserts |
|------|----|----------------|
| `test_healthz.py` | Health | `GET /healthz` → `200 {"status":"ok"}` |
| `test_fr1_upload_video.py` | FR1 | Create video `201` with hashtags, detail `200` with author, 404 on unknown author, 422 on empty caption / zero duration |
| `test_fr2_feed.py` | FR2 | Feed returns structured video items, cursor pagination advances correctly, last page has null cursor, malformed cursor → `400` |
| `test_fr3_playback.py` | FR3 | Manifest returns valid XML MPD with AdaptationSets, segment endpoint returns bytes with `video/mp2t` Content-Type |
| `test_fr4_engagement.py` | FR4 | Like creates row → `200`, unlike → `200`, duplicate like idempotent, like_count increments/decrements; comment create → `201`, list → `200` with cursor |
| `test_fr5_social.py` | FR5 | Follow → `200`, unfollow → `200`, duplicate follow idempotent, follower_count updates, creator catalog returns videos |
| `test_fr6_search.py` | FR6 | Search by caption keyword, hashtag name, username → results; empty query → `200` empty |

---

## Development

```bash
# Install with dev extras
pip install -e ".[dev]"

# Run all unit tests
pytest tests/ -v

# Run a specific test file
pytest tests/test_engagement_service.py -v

# Lint
ruff check src/

# Format
ruff format src/

# Run acceptance tests (against running compose stack)
API_BASE_URL=http://localhost:8010 pytest verify/ -v
```

---

## Design Decisions

For the full treatment — architecture decisions, trade-offs, data model, FR scope, and as-built notes — see [DESIGN.md](DESIGN.md).
