# TikTok/Reels MVP — Design & Module Layout

An MVP short-form video backend that implements the core TikTok browsing and engagement loop. One FastAPI process serves REST endpoints backed by PostgreSQL for metadata and Redis for feed caching. The MVP covers video upload, a recency-biased trending feed, adaptive streaming with mock segments, likes/comments, follow/unfollow with creator catalogs, and Postgres full-text search — minus real GPU transcoding, ML-based recommendation, multi-CDN delivery, Pulsar event streaming, and content moderation.

The broader target — the full TikTok System Design — scales this to 1.9B MAU with GPU-accelerated transcoding, a two-tower online-trained recommendation pipeline, multi-CDN with HyperEdge PCDN, Pulsar for real-time engagement events, and collisionless cuckoo-hash embedding tables. This MVP implements the upload→feed→engage spine that everything else attaches to.

## Architecture

```mermaid
graph TB
    subgraph api["FastAPI App — port 8000"]
        R_FEED[Feed Router<br/>GET /api/v1/feed]
        R_VIDEOS[Videos Router<br/>POST /api/v1/videos<br/>GET /api/v1/videos/:id]
        R_STREAM[Streaming Router<br/>GET /api/v1/videos/:id/manifest<br/>GET /api/v1/segments/:id]
        R_ENGAGE[Engagement Router<br/>POST/DELETE /api/v1/videos/:id/like<br/>POST /api/v1/videos/:id/comments<br/>GET /api/v1/videos/:id/comments]
        R_USERS[Users Router<br/>POST /api/v1/users<br/>GET /api/v1/users/:id<br/>GET /api/v1/users/:id/videos<br/>POST/DELETE /api/v1/users/:id/follow]
        R_SEARCH[Search Router<br/>GET /api/v1/search]
    end

    subgraph services["Service Layer"]
        FS[FeedService<br/>trending scorer, cursor pagination]
        VS[VideoService<br/>upload, detail, hashtag extraction]
        SS[StreamingService<br/>manifest gen, segment lookup]
        ES[EngagementService<br/>like/unlike idempotency, counter flush]
        CS[CommentService<br/>create, list with cursor]
        US[UserService<br/>CRUD, follow, catalog]
        SES[SearchService<br/>FTS tsquery builder]
    end

    subgraph data["Data Layer"]
        PG[(PostgreSQL 16<br/>users, videos, hashtags,<br/>video_hashtags, comments,<br/>likes, follows, video_segments<br/>+ GIN FTS indexes)]
        RD[(Redis<br/>feed:{user_id} sorted sets<br/>counters:{video_id} hashes)]
    end

    R_FEED --> FS
    R_VIDEOS --> VS
    R_STREAM --> SS
    R_ENGAGE --> ES
    R_ENGAGE --> CS
    R_USERS --> US
    R_SEARCH --> SES
    FS --> PG
    FS --> RD
    VS --> PG
    SS --> PG
    ES --> PG
    ES --> RD
    CS --> PG
    US --> PG
    SES --> PG

    classDef rt fill:#d0ebff,stroke:#1c7ed6,color:#1a1a1a
    classDef svc fill:#ffe8cc,stroke:#e8590c,color:#1a1a1a
    classDef store fill:#d3f9d8,stroke:#2f9e44,color:#1a1a1a
    classDef cache fill:#fff3bf,stroke:#f08c00,color:#1a1a1a

    class R_FEED,R_VIDEOS,R_STREAM,R_ENGAGE,R_USERS,R_SEARCH rt
    class FS,VS,SS,ES,CS,US,SES svc
    class PG store
    class RD cache
```

Routers parse HTTP, validate with Pydantic, and delegate to services — no business logic. Services own the domain logic and data access. Redis caches pre-computed feeds per user as sorted sets and denormalized video counters; all authoritiative state lives in Postgres.

## Scope

### In scope

- FR1: Upload and publish a short-form video with caption, hashtags, and sound name
- FR2: View a trending feed (recency-biased score, cursor-paginated, 15 videos/page)
- FR3: Play videos via DASH manifest + mock segment serving (360p/540p/720p)
- FR4: Like videos (idempotent) and post/read comments
- FR5: Follow/unfollow creators, view creator catalog, view user profile
- FR6: Search videos by caption, hashtag, sound name, or creator username
- Plus: `GET /healthz`, `POST /api/v1/users` (MVP setup), seed data utilities

### Out of scope

- Real GPU video transcoding (segments are pre-generated mock `.ts` files)
- ML-based recommendation / two-tower ranking / online training
- Multi-CDN edge delivery / HyperEdge PCDN
- Real-time event streaming (Pulsar/Kafka)
- Content moderation pipeline
- Push notifications
- User authentication (users created via API with no auth)
- Analytics / watch-time tracking
- Share mechanics (count column present, no share endpoint)

## Data Model

```sql
User {
  user_id:          uuid PK
  username:         text UNIQUE
  follower_count:   integer DEFAULT 0    ← denormalized; async consumer would flush
  following_count:  integer DEFAULT 0
  created_at:       timestamp
}

Video {
  video_id:       uuid PK
  author_id:      uuid FK → User
  caption:        text
  sound_name:     text                  ← audio track name (searchable)
  duration_ms:    integer
  like_count:     integer DEFAULT 0     ← denormalized
  comment_count:  integer DEFAULT 0     ← denormalized
  share_count:    integer DEFAULT 0
  created_at:     timestamp
}

Hashtag {
  hashtag_id:  uuid PK
  name:        text UNIQUE
}

VideoHashtag {
  video_id:   uuid PK FK → Video
  hashtag_id: uuid PK FK → Hashtag
}

Comment {
  comment_id:  uuid PK
  video_id:    uuid FK → Video
  user_id:     uuid FK → User
  text:        text
  created_at:  timestamp
}

Like {
  user_id:    uuid PK FK → User
  video_id:   uuid PK FK → Video
  created_at: timestamp
  UNIQUE(user_id, video_id)            ← idempotent like: duplicate returns 200
}

Follow {
  follower_id:  uuid PK FK → User
  followee_id:  uuid PK FK → User
  created_at:   timestamp
  UNIQUE(follower_id, followee_id)     ← idempotent follow
}

VideoSegment {
  segment_id:       uuid PK
  video_id:         uuid FK → Video
  quality:          text               ← enum: 720p, 540p, 360p
  segment_index:    integer
  file_path:        text               ← path to mock .ts file on disk
  duration_seconds: integer
  size_bytes:       integer
  UNIQUE(video_id, quality, segment_index)
}
```

### Key schema decisions

- `Like` has `UNIQUE(user_id, video_id)` — the like endpoint is idempotent. A duplicate like returns HTTP 200 with the current count. Unlike deletes the row and returns 200.
- `Follow` has `UNIQUE(follower_id, followee_id)` — same idempotency pattern as Like. Follow writes the row; unfollow deletes it.
- `follower_count` and `following_count` on User, and `like_count`/`comment_count` on Video are denormalized. In the MVP, the service layer increments/decrements them synchronously on like/unlike and follow/unfollow. The full design would use async Pulsar consumers; MVP trades eventual consistency for simplicity.
- `VideoSegment.file_path` points to a pre-generated mock `.ts` file on disk. The streaming router reads the file and returns raw bytes with `video/mp2t` Content-Type. One mock file per quality tier is reused for every segment of every video — the segment metadata (index, duration) is in the DB; the bytes are static placeholders.
- FTS indexes use a Postgres `tsvector` generated column on `videos` (caption + sound_name + username via JOIN) and a separate `tsvector` on `hashtags` (name), both indexed with GIN. Search UNIONs across both sources.
- Feed scoring uses a recency-biased formula: `score = like_count * 10 + comment_count * 5 + (1.0 / (EXTRACT(EPOCH FROM now() - created_at) / 3600.0 + 2)) * 1000`. Cursor encodes `(score, video_id)` as base64 JSON. No ML — pure SQL sort.

## API Spec

### GET /healthz
Returns `200 {"status": "ok"}` when the app is alive. Used by compose healthcheck and e2e READY probe.

### POST /api/v1/users
Body: `{username}`
Creates a user. Username must be unique.
Response: `201 {user_id, username, follower_count: 0, following_count: 0, created_at}`
Errors: 409 if username taken. 422 if username empty.

### GET /api/v1/users/{user_id}
Returns the user profile with follower/following counts.
Response: `200 {user_id, username, follower_count, following_count, created_at}`
Errors: 404 if not found.

### GET /api/v1/users/{user_id}/videos?cursor=<token>
Creator's published video catalog, reverse-chronological. Cursor encodes `(created_at, video_id)`.
Response: `200 {videos: [{video_id, caption, like_count, comment_count, created_at}, ...], next_cursor: <token>|null}`
Errors: 404 if user not found.

### POST /api/v1/users/{followee_id}/follow?follower_id=<uuid>
Follow a creator. Idempotent — if already following, returns 200.
Response: `200 {"status": "following"}`
Errors: 404 if followee or follower not found. 422 if trying to follow self.

### DELETE /api/v1/users/{followee_id}/follow?follower_id=<uuid>
Unfollow a creator. Idempotent — if not following, still returns 200.
Response: `200 {"status": "unfollowed"}`
Errors: 404 if followee or follower not found.

### POST /api/v1/videos
Body: `{author_id, caption, sound_name, duration_ms, hashtags?: [string]}`
Creates a video. Hashtag names are looked up or created (upsert). Video is immediately `ready` — no transcode pipeline in MVP.
Response: `201 {video_id, author_id, caption, sound_name, duration_ms, like_count: 0, comment_count: 0, share_count: 0, hashtags: [{hashtag_id, name}], created_at}`
Errors: 404 if author_id unknown. 422 if caption empty or duration_ms <= 0.

### GET /api/v1/videos/{video_id}
Video detail with author, hashtags, and engagement counts.
Response: `200 {video_id, caption, sound_name, duration_ms, like_count, comment_count, share_count, author: {user_id, username}, hashtags: [{hashtag_id, name}], created_at}`
Errors: 404 if not found.

### POST /api/v1/videos/{video_id}/segments
Body: `{segments: [{quality, segment_index, file_path, duration_seconds, size_bytes}, ...]}`
Add video segments in bulk. Used during seed data setup. All segments for a video are upserted.
Response: `201 {video_id, segment_count: N}`
Errors: 404 if video not found. 422 if segments list empty or quality invalid.

### GET /api/v1/feed?cursor=<token>
Trending feed, cursor-paginated (15 videos/page). Videos are scored by `score = like_count * 10 + comment_count * 5 + recency_boost` and ordered descending.
Feed is served from Redis sorted set `feed:global` (pre-computed; all users see the same trending feed in MVP). If Redis is cold, the service computes the top 100 directly from Postgres and warms the cache.
Response: `200 {videos: [{video_id, caption, sound_name, author: {user_id, username}, like_count, comment_count, created_at}, ...], next_cursor: <base64 token>|null}`
Errors: 400 if cursor is malformed.

### GET /api/v1/videos/{video_id}/manifest
Returns an MPEG-DASH manifest (.mpd XML) with available quality levels and segment URLs pointing to `GET /api/v1/segments/{segment_id}`.
Errors: 404 if video has no segments.

### GET /api/v1/segments/{segment_id}
Returns raw video bytes for a mock segment. Content-Type: `video/mp2t`. The mock segment is a small pre-generated .ts file (a few KB).
Errors: 404 if segment not found.

### POST /api/v1/videos/{video_id}/like
Like a video (idempotent). Creates the Like row if it doesn't exist; increments `like_count` on Video and Redis counter.
Response: `200 {liked: true, like_count: N}`
Errors: 404 if video or user not found. (user_id passed in body)

### DELETE /api/v1/videos/{video_id}/like
Unlike a video (idempotent). Deletes the Like row if it exists; decrements `like_count`.
Body: `{user_id}`
Response: `200 {liked: false, like_count: N}`
Errors: 404 if video or user not found.

### POST /api/v1/videos/{video_id}/comments
Body: `{user_id, text}`
Post a comment. Increments `comment_count` on Video.
Response: `201 {comment_id, video_id, user_id, text, created_at}`
Errors: 404 if video or user not found. 422 if text empty.

### GET /api/v1/videos/{video_id}/comments?cursor=<token>
List comments for a video, oldest-first. Cursor encodes `(created_at, comment_id)`. Limit 20 per page.
Response: `200 {comments: [{comment_id, text, user: {user_id, username}, created_at}, ...], next_cursor: <token>|null}`
Errors: 404 if video not found.

### GET /api/v1/search?q=<query>&type=hashtag|sound|user|all&cursor=<token>
Full-text search across video captions, hashtags, sound names, and usernames. Uses Postgres `websearch_to_tsquery` across a UNION of tsvector columns. Results ranked by `ts_rank` and recency.
Response: `200 {results: [{type: "video"|"hashtag"|"user", ...matched fields}], next_cursor: <token>|null}`
Errors: 400 if cursor malformed. Empty query returns empty results (200).

## Module Layout

```
src/tiktok_reels/
├── __init__.py
├── main.py                 # create_app() factory, lifespan, /healthz, mount routers
├── config.py               # Settings (pydantic-settings, env-driven)
├── database.py             # async engine/session factory (Postgres), get_session
├── redis.py                # Redis client factory, get_redis dependency
├── models/
│   ├── __init__.py
│   ├── user.py             # User ORM model
│   ├── video.py            # Video ORM model + FTS tsvector column
│   ├── hashtag.py          # Hashtag, VideoHashtag ORM models + FTS tsvector
│   ├── comment.py          # Comment ORM model
│   ├── engagement.py       # Like, Follow ORM models
│   └── segment.py          # VideoSegment ORM model
├── schemas/
│   ├── __init__.py
│   ├── user.py             # UserCreate, UserResponse
│   ├── video.py            # VideoCreate, VideoResponse, VideoDetailResponse, SegmentCreate
│   ├── feed.py             # FeedResponse, FeedItem, CursorToken
│   ├── comment.py          # CommentCreate, CommentResponse, CommentListResponse
│   ├── engagement.py       # LikeResponse, FollowResponse
│   ├── search.py           # SearchResponse, SearchResult
│   └── common.py           # PaginatedResponse, Cursor helpers
├── routers/
│   ├── __init__.py
│   ├── health.py           # GET /healthz
│   ├── users.py            # POST /api/v1/users, GET /api/v1/users/{id}, GET /api/v1/users/{id}/videos, POST|DELETE /api/v1/users/{id}/follow
│   ├── videos.py           # POST /api/v1/videos, GET /api/v1/videos/{id}, POST /api/v1/videos/{id}/segments
│   ├── feed.py             # GET /api/v1/feed
│   ├── streaming.py        # GET /api/v1/videos/{id}/manifest, GET /api/v1/segments/{id}
│   ├── comments.py         # POST /api/v1/videos/{id}/comments, GET /api/v1/videos/{id}/comments
│   ├── engagement.py       # POST|DELETE /api/v1/videos/{id}/like
│   └── search.py           # GET /api/v1/search
└── services/
    ├── __init__.py
    ├── user_service.py     # User CRUD, follow/unfollow with counter updates, creator catalog
    ├── video_service.py    # Video create with hashtag upsert, detail with author/engagement
    ├── feed_service.py     # Trending scorer, cursor encode/decode, Redis sorted set cache
    ├── streaming_service.py # Manifest XML generation, segment file lookup and byte serving
    ├── comment_service.py  # Comment create, paginated list
    ├── engagement_service.py # Like/unlike with denormalized counter + Redis counter
    └── search_service.py   # FTS query builder (websearch_to_tsquery, UNION, ts_rank)
```

## Key Design Decisions

### D1: Feed scoring — trending formula vs. ML ranking

**Decision:** Compute feed order with a recency-biased engagement formula: `score = like_count * 10 + comment_count * 5 + (1.0 / (hours_since_upload + 2)) * 1000`. Cache the top 100 in Redis sorted set `feed:global`. All users see the same trending feed.

Full TikTok uses a two-tower neural net with online-trained collisionless embeddings capable of per-user personalization within 90 seconds of new behavior. That requires GPU inference, parameter servers, Pulsar event streams, and continuous training infrastructure — none of which belong in a single-process FastAPI MVP.

The recency-biased formula achieves a reasonable default feed: fresh videos with engagement surface higher. The `+2` in the denominator prevents brand-new videos (age = 0) from having infinite recency weight. The Redis sorted set makes feed reads sub-millisecond for the common case; a direct Postgres query serves as the cold-start fallback.

**Trade-off:** One global feed vs. per-user personalization. Acceptable for MVP — the feed is "what's trending" not "what's for you." The personalized `feed:{user_id}` key pattern is reserved in Redis for future per-user feeds when recommendations are added.

### D2: Video upload — metadata-only vs. real transcode pipeline

**Decision:** `POST /api/v1/videos` accepts only metadata (caption, sound_name, duration_ms, hashtags). No video file upload. Segments are added separately via `POST /api/v1/videos/{id}/segments` using pre-generated mock .ts files.

Real TikTok uploads involve client-side chunked upload, SHA-256 deduplication, and a 5-variant GPU transcode fan-out with 720p-first priority — a pipeline requiring GPU clusters, object storage, and Pulsar event streams. The MVP's job is to demonstrate the video lifecycle API, not the encoding pipeline. Metadata-only upload keeps the MVP honest: the API contract is real; the bytes behind the segments are placeholders.

### D3: Like/unlike idempotency — UNIQUE constraint vs. application check-then-act

**Decision:** Use Postgres `UNIQUE(user_id, video_id)` on the Like table. Insert on like; if it already exists, catch the integrity error and return 200 with the current count. Delete on unlike.

A check-then-act approach (`SELECT` then `INSERT`) has a race condition between two concurrent likes from the same user — both would pass the check and double-insert. The UNIQUE constraint makes the database the arbiter: the second insert fails cleanly. This is the standard pattern for idempotent one-to-one relationships.

**Trade-off:** The service must catch `IntegrityError` and re-fetch the count, adding a fallback query on the duplicate path. Acceptable since duplicates are rare (the client typically hides the like button after the first tap).

### D4: Search — Postgres FTS vs. Elasticsearch

**Decision:** Use Postgres generated `tsvector` columns with GIN indexes on `videos` (caption + sound_name) and `hashtags` (name), plus a LIKE-based username match. `websearch_to_tsquery` for user-friendly query parsing.

Elasticsearch would be the right choice at TikTok scale (billions of videos, complex relevance scoring, multi-language tokenization). For an MVP with thousands of seed videos, Postgres FTS handles caption/keyword search with zero additional infrastructure. The search service UNIONs results from the video tsvector, hashtag tsvector, and a username ILIKE clause, ranked by `ts_rank` with a recency decay.

### D5: Denormalized counters — synchronous vs. async flush

**Decision:** Increment/decrement `like_count` and `comment_count` on Video, and `follower_count`/`following_count` on User, synchronously within the same transaction as the Like/Comment/Follow write.

The full design uses an async Pulsar consumer that flushes counters independently — trading up to 2 seconds of staleness for eliminating write amplification on every engagement event. At MVP scale (single process, no queue infrastructure), synchronous updates are simpler, always consistent, and add negligible latency. The denormalized columns are structured so migrating to async consumers later requires changing only the service layer, not the schema.

### D6: Cursor pagination — `(score, video_id)` vs. offset

**Decision:** Encode cursor as base64 JSON `{score: float, video_id: uuid}` for the feed, and `{created_at: iso8601, id: uuid}` for comments and catalog listings. Client passes the opaque token back; service decodes and uses it as a WHERE clause anchor.

Offset-based pagination (`LIMIT 15 OFFSET 30`) scans and discards rows. Cursor pagination does a direct index seek from the last-seen position — O(log N) regardless of page depth. For a feed that users scroll dozens of pages deep, this is essential. The cursor is opaque base64 so the client cannot manipulate page boundaries or skip pages.

## Supporting endpoints (not FR-gated, exercised by acceptance test setup)

- `POST /api/v1/users` — create a user → `201`. Duplicate username → `409`.
- `POST /api/v1/videos/{video_id}/segments` — bulk-add mock segments for seed data → `201`.

## Build Plan

Each numbered task below is a kanban card for the build phase. The architect has already produced `design.md` and `verify/acceptance/` — the chain picks up at task 1.

### Tier: senior

1. **Scaffold project skeleton** — `pyproject.toml`, `src/tiktok_reels/` package, `config.py`, `database.py`, `redis.py`, `main.py` with `create_app()` + `/healthz`, `.env.example`, `.gitignore`. App boots and `/healthz` returns 200.

2. **FR5 — User CRUD + follow/unfollow + catalog** — `models/user.py`, `models/engagement.py` (Follow), `schemas/user.py`, `schemas/engagement.py`, `services/user_service.py`, `routers/users.py`. User create with unique username (409 on conflict), follow/unfollow with idempotency and counter updates, creator catalog with cursor pagination.

3. **FR4 — Comments** — `models/comment.py`, `schemas/comment.py`, `services/comment_service.py`, `routers/comments.py`. Post comment (422 empty text, 404 unknown video/user), list comments oldest-first with cursor pagination.

4. **FTS Search** — `models/video.py` (tsvector column + GIN index), `models/hashtag.py`, `services/search_service.py`, `routers/search.py`, `schemas/search.py`. `websearch_to_tsquery`, UNION across video tsvector + hashtag tsvector + username LIKE, ts_rank ordering with recency decay.

5. **Seed data fixtures** — Alembic migration or standalone seed script that creates: ~10 users, ~30 videos with captions/hashtags across ~10 unique hashtags, ~3-5 sound names, segment rows per video (3 quality levels, 3 segments each), 3 mock .ts files (one per quality level), likes/comments/follows to populate the feed.

6. **Docker, Compose & Deploy** — Multi-stage `Dockerfile` (python:3.12-slim), `docker-compose.yml` with `db` + `redis` + `app` services, healthchecks on all three, `APP_PORT` override. `DEPLOY.md` with first-run instructions.

7. **White-box tests** — `tests/conftest.py` + per-service test files under `tests/`. Cover: feed scoring formula, like idempotency, follow counter updates, cursor encode/decode, FTS query building, manifest XML well-formedness.

8. **README + docs** — `README.md` (stack, quick start, API table), `docs/system-design.md` (the full target design), `docs/mvp-scope.md` (this exact cut).

*Note: Acceptance tests (`verify/acceptance/`) are already produced by the architect as part of this card — no separate build task needed.*

### Tier: staff

9. **Data model & Alembic initial migration** — All ORM models: User, Video, Hashtag, VideoHashtag, Comment, Like, Follow, VideoSegment. All constraints, FKs, UNIQUE indexes, and the FTS GIN indexes. Alembic `001_initial` migration that creates every table. This is the foundation every other task builds on — must be correct and complete from the start.

10. **FR1 — Video upload + detail** — `models/video.py`, `models/hashtag.py`, `models/segment.py`, `schemas/video.py`, `services/video_service.py`, `routers/videos.py`. Video create with hashtag upsert (lookup-or-create), video detail with author/engagement/hashtags. Segment bulk insert for seed data.

11. **FR2 — Trending feed** — `services/feed_service.py`, `routers/feed.py`, `schemas/feed.py`. Recency-biased scorer: `score = like_count*10 + comment_count*5 + recency_boost`. Redis sorted set `feed:global` for cached top-100; Postgres fallback on cold cache. Cursor encode/decode with `(score, video_id)`.

12. **FR3 — ABR streaming** — `services/streaming_service.py`, `routers/streaming.py`. Manifest generation: query segments for video_id, build MPD XML with AdaptationSets per quality, SegmentTimeline entries pointing to `/api/v1/segments/{segment_id}`. Segment serving: lookup by id, read mock .ts file, return `video/mp2t`.

13. **FR4 — Like/unlike** — `models/engagement.py` (Like), `schemas/engagement.py`, `services/engagement_service.py`, `routers/engagement.py`. Idempotent like via UNIQUE constraint, synchronous counter increment on Video + Redis `counters:{video_id}:likes`. Unlike deletes row and decrements. Both return current count.

## Acceptance Tests

The `verify/acceptance/` directory contains one executable black-box test file per functional requirement. All tests talk to the running system at `API_BASE_URL` via `httpx` — no app imports. Created as part of this architect card.

| File | FR | What it asserts |
|---|---|---|
| `test_healthz.py` | Health | GET /healthz → 200 |
| `test_fr1_upload_video.py` | FR1 | Video create → 201, detail → 200, hashtag extraction, 404 on unknown author, 422 on empty caption |
| `test_fr2_feed.py` | FR2 | Feed returns videos with expected structure, cursor pagination works, malformed cursor → 400 |
| `test_fr3_playback.py` | FR3 | Manifest returns valid XML with AdaptationSets; segment endpoint returns bytes with correct Content-Type |
| `test_fr4_engagement.py` | FR4 | Like creates → 200, unlike → 200, duplicate like idempotent, like_count increments/decrements; comment create → 201, list → 200 with cursor, empty comment → 422 |
| `test_fr5_social.py` | FR5 | Follow → 200, unfollow → 200, duplicate follow idempotent, follower_count updates, creator catalog returns videos |
| `test_fr6_search.py` | FR6 | Search by caption keyword, hashtag name, username → results; empty query → empty results |

## Conformance to MVP Standards

| # | Standard | Status |
|---|----------|--------|
| 1 | `src/<pkg>/` layout | ✅ `src/tiktok_reels/` planned |
| 2 | routers/services/models/schemas layering | ✅ |
| 3 | app factory + lifespan + `/healthz` | ✅ |
| 4 | `pydantic-settings` config | ✅ |
| 5 | `pyproject.toml` + dev extras | ✅ planned |
| 6 | Alembic migrations | ✅ planned |
| 7 | Multi-stage Dockerfile, py3.12 | ✅ planned |
| 8 | Compose: `db`/`redis`/`app` names, `APP_PORT`, healthcheck | ✅ planned |
| 9 | per-FR acceptance `test_fr<N>_*` | ✅ 7 files (delivered by architect) |
| 10 | `docs/{system-design,mvp-scope,synthesis}.md` | ✅ planned |
| 11 | `DEPLOY.md` | ✅ planned |
| 12 | `.gitignore`, no committed artifacts/`.env` | ✅ planned |
| 13 | env-agnostic product code | ✅ planned |
