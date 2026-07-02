# TikTok/Reels MVP — Design Document

An MVP short-form video backend that implements the core TikTok browsing and engagement loop. One FastAPI process serves REST endpoints backed by PostgreSQL 16 for authoritative metadata and Redis 7 for feed caching and denormalized engagement counters.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                      FastAPI App (Uvicorn)                       │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌────────┐ ┌────────┐ ┌────────┐   │
│  │Users │ │Videos│ │Feed  │ │Stream  │ │Comments│ │Engage  │   │
│  │Router│ │Router│ │Router│ │Router  │ │ Router │ │ Router │   │
│  └──┬───┘ └──┬───┘ └──┬──┘ └───┬────┘ └───┬────┘ └───┬────┘   │
│     │        │        │        │          │          │          │
│  ┌──▼───┐ ┌──▼───┐ ┌──▼──┐ ┌──▼────┐ ┌───▼────┐ ┌───▼────┐   │
│  │User  │ │Video │ │Feed │ │Stream │ │Comment │ │Engage  │   │
│  │Svc   │ │Svc   │ │Svc  │ │Svc    │ │Svc     │ │Svc     │   │
│  └──┬───┘ └──┬───┘ └──┬──┘ └───┬────┘ └───┬────┘ └───┬────┘   │
│     │        │        │        │          │          │          │
│  ┌──▼───┐ ┌──▼────┐                                         │
│  │Search│ │Health │                                         │
│  │Svc   │ │Router │                                         │
│  └──┬───┘ └───────┘                                         │
└─────┼────────────────────────────────────────────────────────┘
      │
      │
┌─────▼────────────────────────────────────────────────────────┐
│                PostgreSQL 16 (async via asyncpg)              │
│  ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌───────────────┐  │
│  │  users   │ │  videos   │ │ hashtags │ │ video_hashtags│  │
│  │  (uuid,  │ │  (uuid,   │ │ (uuid,   │ │ (video_id,    │  │
│  │  username│ │  author,  │ │  name    │ │  hashtag_id)  │  │
│  │  counts) │ │  caption, │ │  UNIQUE) │ │  PK FK pair)  │  │
│  │          │ │  fts gin) │ │          │ │               │  │
│  └──────────┘ └───────────┘ └──────────┘ └───────────────┘  │
│  ┌──────────┐ ┌───────────┐ ┌──────────────┐                │
│  │ comments │ │   likes   │ │   follows   │                │
│  │ (video,  │ │ (user,    │ │ (follower,  │                │
│  │  user,   │ │  video    │ │  followee,  │                │
│  │  text)   │ │  UNIQUE)  │ │  UNIQUE)    │                │
│  └──────────┘ └───────────┘ └──────────────┘                │
│  ┌────────────────────────┐│                                │
│  │    video_segments      ││  GIN indexes:                  │
│  │ (video_id, quality,    ││  - videos (caption + sound)    │
│  │  index, file_path)     ││  - hashtags (name)             │
│  │ UNIQUE(vid,q,idx)      ││                                │
│  └────────────────────────┘│                                │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────▼───────────────────────────────┐
│                   Redis 7 (optional)                         │
│  ┌────────────────────┐  ┌──────────────────────────────┐   │
│  │ feed:global        │  │ counters:{video_id}          │   │
│  │ (sorted set,       │  │ (hash — like_count,          │   │
│  │  top-100 scored)   │  │  comment_count)              │   │
│  └────────────────────┘  └──────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**Layering rules:**
- **Routers** (`routers/`): Parse HTTP, validate with Pydantic schemas, delegate to services. No business logic.
- **Services** (`services/`): Own domain logic and data access. Each service maps to one domain aggregate (UserService, VideoService, FeedService, etc.).
- **Models** (`models/`): SQLAlchemy ORM, one file per aggregate. `Base` in `base.py`; every model extends it.
- **Schemas** (`schemas/`): Pydantic v2 models for request validation and response serialization. `from_attributes` enabled for ORM-to-DTO mapping.

---

## Functional Requirements (built)

| ID | Description | Route | Status |
|----|------------|-------|--------|
| FR1 | Upload and publish a short-form video with caption, hashtags, and sound name | `POST /api/v1/videos` | Built — metadata-only upload, hashtag upsert, `201` with full response |
| FR2 | View a trending feed (recency-biased, cursor-paginated, 15/page) | `GET /api/v1/feed` | Built — `score = like_count*10 + comment_count*5 + recency_boost`, Redis cache |
| FR3 | Play videos via DASH manifest with adaptive quality tiers | `GET /api/v1/videos/{id}/manifest`, `GET /api/v1/segments/{id}` | Built — MPD XML with AdaptationSets per quality, mock `.ts` byte serving |
| FR4 | Like/unlike videos (idempotent) and post/read comments | `POST/DELETE /api/v1/videos/{id}/like`, `POST/GET /api/v1/videos/{id}/comments` | Built — UNIQUE constraint for idempotency, denormalized counters |
| FR5 | Follow/unfollow creators, view creator catalog, view user profile | `POST/DELETE /api/v1/users/{id}/follow`, `GET /api/v1/users/{id}/videos`, `GET /api/v1/users/{id}` | Built — idempotent follow/unfollow, counter updates, cursor-paginated catalog |
| FR6 | Search videos by caption, hashtag, sound name, or creator username | `GET /api/v1/search` | Built — Postgres `websearch_to_tsquery`, UNION across 3 entity types |
| HZ | Health check | `GET /healthz` | Built — `200 {"status":"ok"}`, used by compose healthcheck and CI readiness probe |

### Out of scope (deliberately cut for MVP)

Real GPU video transcoding, ML-based recommendation / two-tower ranking, multi-CDN edge delivery, real-time event streaming (Pulsar/Kafka), content moderation pipeline, push notifications, user authentication, watch-time analytics, share mechanics (count column exists, no share endpoint).

---

## Data Model

### Entity Relationship Summary

```
User ──1:N──> Video      (author)
User ──1:N──> Comment    (commenter)
User ──1:N──> Like       (liker)
User ──1:N──> Follow     (follower)
User ──1:N──> Follow     (followee)
Video ──1:N──> Comment   (video's comments)
Video ──1:N──> Like      (video's likes)
Video ──1:N──> VideoSegment (ABR segments)
Video ──M:N──> Hashtag   (via VideoHashtag junction)
```

### Table: `users`

| Column | Type | Constraints | Notes |
|--------|------|------------|-------|
| `user_id` | `uuid` | PK, default `uuid4()` | |
| `username` | `varchar(50)` | UNIQUE, NOT NULL, INDEX | |
| `follower_count` | `integer` | DEFAULT 0, NOT NULL | Denormalized — updated synchronously on follow/unfollow |
| `following_count` | `integer` | DEFAULT 0, NOT NULL | Denormalized — same transaction as follow row |
| `created_at` | `timestamptz` | NOT NULL, `now()` | |

### Table: `videos`

| Column | Type | Constraints | Notes |
|--------|------|------------|-------|
| `video_id` | `uuid` | PK, default `uuid4()` | |
| `author_id` | `uuid` | FK → `users.user_id`, NOT NULL, INDEX | |
| `caption` | `text` | NOT NULL | |
| `sound_name` | `varchar(255)` | NOT NULL, DEFAULT 'original sound' | Searchable via FTS |
| `duration_ms` | `integer` | NOT NULL | |
| `like_count` | `integer` | DEFAULT 0, NOT NULL | Denormalized — synchronous increment |
| `comment_count` | `integer` | DEFAULT 0, NOT NULL | Denormalized — synchronous increment |
| `share_count` | `integer` | DEFAULT 0, NOT NULL | Reserved — no share endpoint in MVP |
| `created_at` | `timestamptz` | NOT NULL, `now()` | |

### Table: `hashtags`

| Column | Type | Constraints |
|--------|------|------------|
| `hashtag_id` | `uuid` | PK, default `uuid4()` |
| `name` | `varchar(100)` | UNIQUE, NOT NULL, INDEX |

### Table: `video_hashtags` (junction)

| Column | Type | Constraints |
|--------|------|------------|
| `video_id` | `uuid` | PK, FK → `videos.video_id` ON DELETE CASCADE |
| `hashtag_id` | `uuid` | PK, FK → `hashtags.hashtag_id` ON DELETE CASCADE |

### Table: `comments`

| Column | Type | Constraints |
|--------|------|------------|
| `comment_id` | `uuid` | PK, default `uuid4()` |
| `video_id` | `uuid` | FK → `videos.video_id` ON DELETE CASCADE, NOT NULL, INDEX |
| `user_id` | `uuid` | FK → `users.user_id` ON DELETE CASCADE, NOT NULL |
| `text` | `text` | NOT NULL |
| `created_at` | `timestamptz` | NOT NULL, `now()` |

### Table: `likes`

| Column | Type | Constraints |
|--------|------|------------|
| `user_id` | `uuid` | PK, FK → `users.user_id` ON DELETE CASCADE |
| `video_id` | `uuid` | PK, FK → `videos.video_id` ON DELETE CASCADE |
| `created_at` | `timestamptz` | NOT NULL, `now()` |

**UNIQUE constraint:** `(user_id, video_id)` — enforces idempotent likes at the database level.

### Table: `follows`

| Column | Type | Constraints |
|--------|------|------------|
| `follower_id` | `uuid` | PK, FK → `users.user_id` ON DELETE CASCADE |
| `followee_id` | `uuid` | PK, FK → `users.user_id` ON DELETE CASCADE |
| `created_at` | `timestamptz` | NOT NULL, `now()` |

**UNIQUE constraint:** `(follower_id, followee_id)` — enforces idempotent follows at the database level.

### Table: `video_segments`

| Column | Type | Constraints |
|--------|------|------------|
| `segment_id` | `uuid` | PK, default `uuid4()` |
| `video_id` | `uuid` | FK → `videos.video_id` ON DELETE CASCADE, NOT NULL, INDEX |
| `quality` | `varchar(10)` | NOT NULL — values: `360p`, `540p`, `720p`, `1080p` |
| `segment_index` | `integer` | NOT NULL |
| `file_path` | `text` | NOT NULL — path to mock `.ts` file on disk |
| `duration_seconds` | `integer` | NOT NULL |
| `size_bytes` | `integer` | NOT NULL |

**UNIQUE constraint:** `(video_id, quality, segment_index)` — one row per quality tier per segment index.

---

## Key Design Decisions

### D1: Feed Scoring — Engagement Formula vs. ML Ranking

**Decision:** Compute feed order with a recency-biased engagement formula in SQL. Cache the top 100 scored videos in Redis sorted set `feed:global`. All users see the same trending feed.

```
score = like_count * 10 + comment_count * 5 + (1.0 / (hours_since_upload + 2)) * 1000
```

**Why this choice:** Full TikTok uses a two-tower neural net with online-trained embeddings for per-user personalization — requiring GPU inference, parameter servers, Pulsar event streams, and continuous training. None of that belongs in a single-process FastAPI MVP. The formula produces a reasonable default feed: fresh videos with engagement surface higher. The `+2` in the denominator prevents brand-new videos (age = 0) from having infinite recency weight.

**Trade-off:** One global feed vs. per-user personalization. Acceptable for MVP — it's "what's trending" not "what's for you." The `feed:{user_id}` key pattern is reserved for future per-user feeds.

**Evidence:** See `src/tiktok_reels/services/feed_service.py` lines 136–139 for the SQL formula, and lines 211–216 for the Redis cache warming logic.

### D2: Video Upload — Metadata-Only vs. Transcode Pipeline

**Decision:** `POST /api/v1/videos` accepts only metadata (caption, sound_name, duration_ms, hashtags). Segments are added separately via `POST /api/v1/videos/{id}/segments` using pre-generated mock `.ts` files.

**Why this choice:** Real TikTok uploads involve client-side chunked upload, SHA-256 deduplication, and a 5-variant GPU transcode fan-out — requiring GPU clusters, object storage, and Pulsar event streams. The MVP's job is to demonstrate the video lifecycle API, not the encoding pipeline. Metadata-only upload keeps the API contract real while the bytes behind the segments are placeholders.

**Trade-off:** No real video transcoding. The API contract (manifest, segments, content type) works; the actual bytes are small mock files.

**Evidence:** `src/tiktok_reels/routers/videos.py` lines 19–51 — video creation accepts `VideoCreate` with `author_id`, `caption`, `sound_name`, `duration_ms`, `hashtags`. The streaming router returns either a real `.ts` file or a fallback of 3×188-byte sync packets (`src/tiktok_reels/routers/streaming.py` lines 52–54).

### D3: Like/Follow Idempotency — UNIQUE Constraint vs. Application Check

**Decision:** Use Postgres `UNIQUE(user_id, video_id)` on the Like table and `UNIQUE(follower_id, followee_id)` on the Follow table. Insert on like/follow; if it already exists, the constraint violation signals idempotency and the endpoint returns 200.

**Why this choice:** A check-then-act approach (`SELECT` then `INSERT`) has a race condition between two concurrent operations — both would pass the check and double-insert. The UNIQUE constraint makes the database the arbiter: the second insert fails cleanly. This is the standard pattern for idempotent one-to-one relationships.

**Trade-off:** The service must handle the conflict gracefully. In practice, duplicates are rare (the client hides the like button after the first tap). The current implementation checks first (`SELECT` before `INSERT`) for simplicity at MVP scale; a migration to catch-and-ignore is the production path.

**Evidence:** `src/tiktok_reels/models/engagement.py` lines 13 and 38–39 — `UniqueConstraint` definitions. `src/tiktok_reels/services/engagement_service.py` lines 31–39 — check for existing like. `src/tiktok_reels/services/user_service.py` lines 42–48 — check for existing follow.

### D4: Search — Postgres FTS vs. Elasticsearch

**Decision:** Use Postgres `websearch_to_tsquery` across generated `tsvector` columns with GIN indexes on `videos` (caption + sound_name) and `hashtags` (name), plus a LIKE-based username match.

**Why this choice:** Elasticsearch would be right at TikTok scale (billions of videos, complex relevance, multi-language tokenization). For an MVP with thousands of seed videos, Postgres FTS handles caption/keyword search with zero additional infrastructure. The search UNIONs results from video FTS, hashtag FTS, and username ILIKE.

**Evidence:** `src/tiktok_reels/services/search_service.py` — `_search_videos` (line 54), `_search_hashtags` (line 83), `_search_users` (line 99) — three separate queries UNIONed in the service layer.

### D5: Denormalized Counters — Synchronous vs. Async Flush

**Decision:** Increment/decrement `like_count` and `comment_count` on Video, and `follower_count`/`following_count` on User, synchronously within the same transaction as the Like/Comment/Follow write.

**Why this choice:** The full design uses an async Pulsar consumer that flushes counters independently — trading up to 2 seconds of staleness for eliminating write amplification on every engagement event. At MVP scale (single process, no queue infrastructure), synchronous updates are simpler, always consistent, and add negligible latency.

**Trade-off:** The columns are structured so migrating to async consumers later requires changing only the service layer, not the schema. The Redis `counters:{video_id}` hash is written alongside the DB counter for future hot-path reads.

**Evidence:** `src/tiktok_reels/services/engagement_service.py` lines 46–50 — synchronous counter increment on `Video.like_count`. `src/tiktok_reels/services/user_service.py` lines 55–64 — synchronous updates to `User.following_count` and `User.follower_count`.

### D6: Cursor Pagination — `(score, video_id)` Token vs. Offset

**Decision:** Encode cursor as base64 JSON pairs — `{score, video_id}` for the feed, `{created_at, id}` for comments and catalog listings. Client passes the opaque token back; the service decodes and uses it as a WHERE clause anchor.

**Why this choice:** Offset-based pagination (`LIMIT 15 OFFSET 30`) scans and discards rows. Cursor pagination does a direct index seek from the last-seen position — O(log N) regardless of page depth. For a feed that users scroll hundreds of pages deep, this is essential. The cursor is opaque base64 so the client cannot manipulate page boundaries.

**Evidence:** `src/tiktok_reels/schemas/common.py` — `encode_cursor` (line 17), `encode_cursor_datetime` (line 35), `decode_cursor` (line 41). Used by `FeedService` (feed lines 93–102), `CommentService` (comments line 89), and `UserService` (catalog line 133).

---

## Cursor Pagination Design

```
Feed:     encode({score, video_id, ts?})  → base64 JSON → opaque token
Comments: encode({created_at, id})         → base64 JSON → opaque token
Catalog:  encode({created_at, id})         → base64 JSON → opaque token
Search:   offset-based (int cursor)        → UNION makes score-based complex in MVP
```

The feed cursor optionally embeds a stable reference timestamp (`ts`). When present, the feed SQL uses this frozen timestamp instead of `func.now()` so scores don't drift between pages of the same pagination session.

**Edge case:** If a video is deleted between page 1 and page 2, the cursor might point to a removed ID. The WHERE clause uses `< score` and falls back to `video_id < :cid` on exact-score ties — a deleted video at the boundary leaves a gap of one item on the next page. Acceptable for MVP.

---

## Feed Scoring Formula

```
score = like_count * 10
      + comment_count * 5
      + (1.0 / (EXTRACT(EPOCH FROM now() - created_at) / 3600.0 + 2)) * 1000
```

- Engagement weight: 10 per like, 5 per comment
- Recency bonus: decays as 1000 / (hours_since_upload + 2)
- At upload time (0 hours): recency bonus = 500
- After 1 hour: recency bonus ≈ 333
- After 24 hours: recency bonus ≈ 38
- After 7 days (168 hours): recency bonus ≈ 5.9

A video with 10 likes and 5 comments uploaded 1 hour ago scores: `10*10 + 5*5 + 333 = 458`.

---

## Acceptance Test Coverage Map

| File | FR | Route(s) | Assertions |
|------|----|----------|------------|
| `test_healthz.py` | HZ | `GET /healthz` | 200 + `{"status":"ok"}` |
| `test_fr1_upload_video.py` | FR1 | `POST /api/v1/videos`, `GET /api/v1/videos/{id}` | 201 with caption/hashtags, 404 on unknown author, 422 on empty caption / zero duration, hashtag dedup |
| `test_fr2_feed.py` | FR2 | `GET /api/v1/feed?cursor=` | 200 with structured items, cursor pagination, disjoint pages, malformed cursor → 400 |
| `test_fr3_playback.py` | FR3 | `GET /api/v1/videos/{id}/manifest`, `GET /api/v1/segments/{id}` | Valid MPD XML, AdaptationSets, `video/mp2t` Content-Type |
| `test_fr4_engagement.py` | FR4 | `POST/DELETE /api/v1/videos/{id}/like`, `POST/GET /api/v1/videos/{id}/comments` | Like/unlike 200, idempotency, counter accuracy, comment create/list, cursor |
| `test_fr5_social.py` | FR5 | `POST/DELETE /api/v1/users/{id}/follow`, `GET /api/v1/users/{id}/videos` | Follow/unfollow 200, idempotency, follower_count updates, catalog |
| `test_fr6_search.py` | FR6 | `GET /api/v1/search?q=&type=` | Results by caption/hashtag/username, empty query → 200 empty |

---

## CI/CD Pipeline

Three GitHub Actions workflows (see `.github/workflows/`):

| Workflow | Trigger | Steps |
|----------|---------|-------|
| `lint.yml` | PR + push to main | Ruff check + format (pinned 0.15.20) |
| `ci.yml` | PR + push to main | Postgres 16 service container, run 40 unit tests via pytest |
| `functional.yml` | Push to main | Full compose stack (db + redis + app), migrations, 7 acceptance tests via httpx |

---

## Key Files

| File | Size | Purpose |
|------|------|---------|
| `src/tiktok_reels/main.py` | 34 lines | App factory with lifespan, `/healthz`, router mounting |
| `src/tiktok_reels/config.py` | 12 lines | Pydantic-settings, env-driven config |
| `src/tiktok_reels/database.py` | 24 lines | Async SQLAlchemy engine (pool_size=10, max_overflow=20) |
| `src/tiktok_reels/redis.py` | 30 lines | Redis client factory, graceful None on missing Redis |
| `src/tiktok_reels/routers/` | 7 routers | One file per domain aggregate, thin HTTP → service delegation |
| `src/tiktok_reels/services/` | 7 services | All business logic and data access |
| `src/tiktok_reels/models/` | 7 model files | SQLAlchemy ORM, 8 tables total |
| `src/tiktok_reels/schemas/` | 8 schema files | Pydantic v2 request/response models |
| `tests/` | 6 test files | 40 unit tests using SQLite in-memory DB |
| `verify/acceptance/` | 7 test files + conftest | Black-box acceptance tests against compose stack |
| `docker-compose.yml` | 87 lines | `db` + `redis` + `app`, named network, healthchecks, `APP_PORT` override |
| `Dockerfile` | 34 lines | Multi-stage build, `python:3.12-slim` |
| `DEPLOY.md` | Production deployment instructions, health check table, CI/CD workflow list |
