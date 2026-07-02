# TikTok/Reels MVP — Build Spec

## 1. Goal & scope

Build a backend MVP implementing the core TikTok/Reels loop: publish a short-form video, browse a
trending feed, play it back via adaptive streaming, engage (like/comment), follow creators, and search.
One FastAPI process serves REST endpoints backed by PostgreSQL 16 for authoritative metadata and
Redis 7 for feed caching and denormalized engagement counters. Segment bytes are mock `.ts` files —
the API contract for adaptive playback is real; the encoding pipeline is not.

**In scope**
- Metadata-only video publish with caption, sound name, duration, and hashtag upsert
- Trending feed: recency-biased engagement score, Redis-cached top-100, cursor-paginated (15/page)
- MPEG-DASH playback: MPD manifest with an AdaptationSet per quality tier (`360p`–`1080p`) + segment byte serving
- Idempotent like/unlike with synchronous denormalized counters
- Comments: post + oldest-first cursor-paginated listing (20/page)
- Follow/unfollow (idempotent), user profiles with follower/following counts, creator video catalog
- Full-text search (Postgres FTS) across captions, sound names, hashtags, plus username match
- Health endpoint for compose healthchecks and CI readiness probes

**Out of scope**
- Real GPU video transcoding (segments are pre-registered mock files)
- ML-based recommendation / two-tower per-user ranking (one global trending feed)
- Multi-CDN edge delivery
- Real-time event streaming (Pulsar/Kafka) — counters update synchronously in-transaction
- Content moderation pipeline
- Push notifications
- User authentication (caller passes `user_id` explicitly)
- Watch-time analytics
- Share mechanics (`share_count` column reserved, no endpoint)

## 2. Functional requirements

- **FR-1 — Publish a video.** Metadata-only upload with hashtag upsert (deduped, case-normalized).
  `POST /api/v1/videos {author_id, caption, sound_name, duration_ms, hashtags}` → `201` with full
  video response; unknown author → `404`; empty caption / zero duration → `422`.
- **FR-2 — Trending feed.** Recency-biased engagement ranking, same feed for all users.
  `score = like_count*10 + comment_count*5 + 1000/(hours_since_upload + 2)`; top-100 cached in the
  Redis sorted set `feed:global`.
  `GET /api/v1/feed?cursor=` → `200`, 15 items/page, opaque base64 cursor; malformed cursor → `400`.
- **FR-3 — Playback.** DASH manifest plus segment serving.
  `GET /api/v1/videos/{video_id}/manifest` → MPD XML with an AdaptationSet per quality; no segments → `404`.
  `GET /api/v1/segments/{segment_id}` → segment bytes, `Content-Type: video/mp2t`; unknown → `404`.
  `POST /api/v1/videos/{video_id}/segments` bulk-registers quality/index/file-path rows.
- **FR-4 — Engagement.** Idempotent likes + comments with accurate denormalized counters.
  `POST/DELETE /api/v1/videos/{video_id}/like?user_id=` → `200` (duplicate like/unlike is a no-op);
  `POST /api/v1/videos/{video_id}/comments` → `201`; `GET .../comments` → oldest-first, 20/page cursor;
  unknown video/user → `404`.
- **FR-5 — Social graph.** Follow/unfollow, profile, creator catalog.
  `POST/DELETE /api/v1/users/{followee_id}/follow?follower_id=` → `200`, idempotent; self-follow → `422`;
  `GET /api/v1/users/{user_id}` → profile with follower/following counts;
  `GET /api/v1/users/{user_id}/videos` → reverse-chronological cursor-paginated catalog.
  `POST /api/v1/users {username}` → `201`; duplicate username → `409`.
- **FR-6 — Search.** Postgres `websearch_to_tsquery` over GIN-indexed tsvectors (video caption +
  sound name, hashtag name) unioned with username ILIKE.
  `GET /api/v1/search?q=&type=all|video|hashtag|user` → `200`; empty query → `200` empty result.
- **HZ — Health.** `GET /healthz` → `200 {"status":"ok"}`.

## 3. Stack & deployment

- **Runtime:** Python 3.12, FastAPI, uvicorn
- **Datastore:** PostgreSQL 16 (async via asyncpg), SQLAlchemy 2.0 async ORM + Alembic migrations
- **Cache:** Redis 7 (redis-py async) — optional; the app degrades to SQL-only feeds when absent
- **Tests:** pytest — unit suite on SQLite in-memory (no external deps) + httpx black-box acceptance
  suite against the running compose stack
- **Container:** Docker Compose (`db` + `redis` + `app`) with healthchecks and a named network;
  host port `APP_PORT` (default 8010) maps to in-container 8000

Design → [DESIGN.md](DESIGN.md)

## 4. Data model

```sql
User {
  user_id:         uuid PK
  username:        varchar(50) UNIQUE
  follower_count:  integer     ← denormalized, updated in the follow/unfollow transaction
  following_count: integer     ← denormalized, same transaction
  created_at:      timestamptz
}

Video {
  video_id:      uuid PK
  author_id:     uuid FK → User
  caption:       text
  sound_name:    varchar(255)  ← searchable via FTS, default 'original sound'
  duration_ms:   integer
  like_count:    integer       ← denormalized, synchronous increment
  comment_count: integer       ← denormalized, synchronous increment
  share_count:   integer       ← reserved, no share endpoint in MVP
  created_at:    timestamptz
  fts:           tsvector      ← generated (caption + sound_name), GIN index
}

Hashtag {
  hashtag_id: uuid PK
  name:       varchar(100) UNIQUE  ← GIN FTS index
}

VideoHashtag {
  video_id:   uuid PK, FK → Video ON DELETE CASCADE
  hashtag_id: uuid PK, FK → Hashtag ON DELETE CASCADE
}

Comment {
  comment_id: uuid PK
  video_id:   uuid FK → Video ON DELETE CASCADE
  user_id:    uuid FK → User ON DELETE CASCADE
  text:       text
  created_at: timestamptz
}

Like {
  user_id:    uuid PK, FK → User
  video_id:   uuid PK, FK → Video
  created_at: timestamptz
  UNIQUE(user_id, video_id)          ← database-enforced idempotency
}

Follow {
  follower_id: uuid PK, FK → User
  followee_id: uuid PK, FK → User
  created_at:  timestamptz
  UNIQUE(follower_id, followee_id)   ← database-enforced idempotency
}

VideoSegment {
  segment_id:       uuid PK
  video_id:         uuid FK → Video ON DELETE CASCADE
  quality:          varchar(10)     ← 360p | 540p | 720p | 1080p
  segment_index:    integer
  file_path:        text            ← mock .ts file on disk
  duration_seconds: integer
  size_bytes:       integer
  UNIQUE(video_id, quality, segment_index)
}
```

## 5. API

- `GET /healthz` — liveness probe
- `POST /api/v1/users` — create user
- `GET /api/v1/users/{user_id}` — user profile with counts
- `GET /api/v1/users/{user_id}/videos` — creator catalog (cursor-paginated)
- `POST /api/v1/users/{followee_id}/follow` — follow a creator (idempotent)
- `DELETE /api/v1/users/{followee_id}/follow` — unfollow (idempotent)
- `POST /api/v1/videos` — publish video metadata with hashtag upsert
- `GET /api/v1/videos/{video_id}` — video detail with author, hashtags, counts
- `POST /api/v1/videos/{video_id}/segments` — bulk-register ABR segments
- `GET /api/v1/feed` — trending feed (cursor-paginated, 15/page)
- `GET /api/v1/videos/{video_id}/manifest` — MPEG-DASH MPD manifest
- `GET /api/v1/segments/{segment_id}` — segment bytes (`video/mp2t`)
- `POST /api/v1/videos/{video_id}/like` — like (idempotent)
- `DELETE /api/v1/videos/{video_id}/like` — unlike (idempotent)
- `POST /api/v1/videos/{video_id}/comments` — post comment
- `GET /api/v1/videos/{video_id}/comments` — list comments (cursor-paginated, 20/page)
- `GET /api/v1/search` — FTS across videos, hashtags, usernames

## 6. Test scenarios

- Idempotent like: like the same video twice → both `200`, `like_count` incremented once
- Idempotent follow: duplicate follow → `200`, `follower_count` unchanged; self-follow → `422`
- Counter accuracy: like → unlike → `like_count` returns to original value
- Feed pagination: consecutive pages are disjoint; last page returns null cursor; malformed cursor → `400`
- Stable pagination session: feed cursor embeds a frozen reference timestamp so scores don't drift between pages
- Hashtag dedup: publishing with duplicate hashtags stores each hashtag once
- Validation: empty caption / zero duration → `422`; unknown author on publish → `404`
- Manifest correctness: MPD is valid XML with one AdaptationSet per registered quality tier
- Segment serving: bytes returned with `Content-Type: video/mp2t`; unknown segment → `404`
- Search coverage: hits by caption keyword, hashtag name, and username; empty query → `200` empty
- Comment flow: post → `201`; list is oldest-first with working cursor pagination
- Duplicate username on user create → `409`

## 7. Module layout

```
src/tiktok_reels/
  main.py                 # app factory, lifespan, /healthz, router mounting
  config.py               # pydantic-settings, env-driven
  database.py             # async SQLAlchemy engine + session factory
  redis.py                # Redis async client factory (graceful None when absent)
  routers/
    users.py              # user CRUD + follow/unfollow + catalog
    videos.py             # publish + detail + segment registration
    feed.py               # trending feed
    streaming.py          # MPD manifest + segment bytes
    comments.py           # post/list comments
    engagement.py         # like/unlike
    search.py             # FTS search
    health.py             # /healthz
  services/
    user_service.py, video_service.py, feed_service.py,
    streaming_service.py, comment_service.py,
    engagement_service.py, search_service.py
  models/                 # SQLAlchemy ORM — user, video, hashtag, comment, engagement, segment
  schemas/                # Pydantic v2 request/response models + cursor helpers (common.py)
alembic/
  versions/               # migrations
tests/                    # 40 unit/integration tests (SQLite in-memory)
verify/
  acceptance/             # black-box HTTP acceptance tests (one file per FR + healthz)
```

## 8. Run

```bash
docker compose up --build -d
docker compose exec app alembic upgrade head
curl http://localhost:8010/healthz
pytest tests/ -v
API_BASE_URL=http://localhost:8010 pytest verify/acceptance -v
```
