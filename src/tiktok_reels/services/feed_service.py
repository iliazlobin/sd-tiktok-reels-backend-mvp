import json
import uuid
from base64 import b64decode, b64encode
from datetime import datetime

from sqlalchemy import bindparam, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.types import DateTime

from tiktok_reels.models.video import Video
from tiktok_reels.schemas.common import decode_cursor, encode_cursor
from tiktok_reels.schemas.feed import FeedItem, UserBriefResponse


class FeedService:
    """Trending feed scorer, cursor encode/decode, Redis sorted set cache."""

    FEED_CACHE_KEY = "feed:global"
    FEED_CACHE_SIZE = 100
    PAGE_SIZE = 15

    def __init__(self, session: AsyncSession, redis_client=None) -> None:
        self.session = session
        self.redis = redis_client

    async def get_feed(self, cursor: str | None = None) -> tuple[list[FeedItem], str | None]:
        """Get trending feed, cursor-paginated. Tries Redis cache first, falls back to Postgres."""
        # Try Redis cache first
        if self.redis:
            try:
                items = await self._get_cached_feed(cursor)
                if items is not None:
                    return items
            except Exception:
                pass

        # Fallback: query from Postgres
        return await self._compute_feed(cursor)

    async def _get_cached_feed(
        self,
        cursor: str | None = None,
    ) -> tuple[list[FeedItem], str | None] | None:
        """Fetch feed from Redis sorted set. Returns None if cache is cold."""
        # Get the sorted set
        raw = await self.redis.zrevrange(
            self.FEED_CACHE_KEY, 0, self.FEED_CACHE_SIZE - 1, withscores=True
        )
        if not raw:
            return None

        # Parse cache entries: {video_id: score}
        cached: list[tuple[str, float]] = []
        for video_id_bytes, score in raw:
            video_id = (
                video_id_bytes if isinstance(video_id_bytes, str) else video_id_bytes.decode()
            )
            cached.append((video_id, score))

        # Apply cursor offset
        start_idx = 0
        if cursor:
            try:
                cursor_data = json.loads(b64decode(cursor.encode()).decode())
                for i, (vid, _) in enumerate(cached):
                    if vid == cursor_data.get("id"):
                        start_idx = i + 1
                        break
            except Exception as exc:
                raise ValueError("malformed cursor") from exc

        page = cached[start_idx : start_idx + self.PAGE_SIZE]
        if not page:
            return [], None

        # Fetch full video details from DB
        video_ids = [uuid.UUID(vid) for vid, _ in page]
        if not video_ids:
            return [], None

        result = await self.session.execute(
            select(Video).options(selectinload(Video.author)).where(Video.video_id.in_(video_ids)),
        )
        videos_map = {v.video_id: v for v in result.scalars().all()}

        feed_items = []
        for vid, score in page:
            v = videos_map.get(uuid.UUID(vid))
            if v:
                feed_items.append(self._video_to_feed_item(v, score))

        next_cursor = None
        if len(cached) > start_idx + self.PAGE_SIZE:
            last_id = page[-1][0]
            next_payload = b64encode(
                json.dumps(
                    {"score": page[-1][1], "id": last_id},
                    separators=(",", ":"),
                ).encode()
            ).decode()
            next_cursor = next_payload

        return feed_items, next_cursor

    async def _compute_feed(
        self,
        cursor: str | None = None,
    ) -> tuple[list[FeedItem], str | None]:
        """Compute feed directly from Postgres using the recency-biased formula.

        Scores use a recency-weighted formula (like_count * 10 + comment_count * 5 +
        recency_bonus).  To keep cursor pagination stable across pages the
        reference timestamp is **frozen** at the first page's ``now()`` and
        embedded in the cursor.  Every subsequent page uses the same timestamp
        so scores don't drift between pages.
        """
        cursor_score: float | None = None
        cursor_vid: uuid.UUID | None = None

        if cursor:
            cursor_data = decode_cursor(cursor)
            cursor_score = float(cursor_data["score"])
            cursor_vid = uuid.UUID(cursor_data["id"])
            ref_ts = cursor_data.get("ts")
        else:
            ref_ts = None

        # Use a stable reference timestamp if this is a follow-up page
        if ref_ts:
            ref_ts_dt = datetime.fromisoformat(ref_ts)
            now = bindparam("_feed_ref_ts", value=ref_ts_dt, type_=DateTime(timezone=True))
        else:
            now = func.now()

        score_expr = (
            Video.like_count * 10
            + Video.comment_count * 5
            + (1.0 / (func.extract("epoch", now - Video.created_at) / 3600.0 + 2)) * 1000
        ).label("score")

        # Build the score formula text HERE — before the query — so it can be
        # used in BOTH the ORDER BY and the WHERE clause. Using the identical
        # expression in both places eliminates floating-point precision drift
        # between the SELECT-computed alias and the WHERE recomputation, which
        # caused overlapping pages when all items had identical scores.
        if ref_ts:
            score_formula = (
                "videos.like_count * 10 + videos.comment_count * 5 + "
                "(1.0 / (EXTRACT(EPOCH FROM ("
                f"'{ref_ts}'::timestamptz - videos.created_at"
                ")) / 3600.0 + 2)) * 1000"
            )
        else:
            score_formula = (
                "videos.like_count * 10 + videos.comment_count * 5 + "
                "(1.0 / (EXTRACT(EPOCH FROM (now() - videos.created_at)) / 3600.0 + 2)) * 1000"
            )

        query = (
            select(Video, score_expr)
            .options(selectinload(Video.author))
            .order_by(text(f"({score_formula}) DESC"), Video.video_id.desc())
        )

        if cursor:
            try:
                query = query.where(
                    text(
                        f"({score_formula}) < :cs "
                        f"OR (({score_formula}) = :cs AND videos.video_id < :cid)"
                    ).bindparams(cs=cursor_score, cid=cursor_vid),
                )
            except (ValueError, KeyError, TypeError) as exc:
                raise ValueError("malformed cursor") from exc

        result = await self.session.execute(query.limit(self.PAGE_SIZE + 1))
        rows = result.all()

        feed_items: list[FeedItem] = []
        for row in rows:
            video, score = row
            feed_items.append(self._video_to_feed_item(video, score))

        next_cursor = None
        if len(feed_items) > self.PAGE_SIZE:
            feed_items = feed_items[: self.PAGE_SIZE]
            last = rows[self.PAGE_SIZE - 1]
            last_video, last_score = last[0], last[1]
            # Capture a stable timestamp on the first page so follow-up
            # pagination uses consistent scores.
            if ref_ts is None and cursor is None:
                result_ts = await self.session.execute(text("SELECT now()"))
                ref_ts = result_ts.scalar().isoformat()
            next_cursor = encode_cursor(float(last_score), last_video.video_id, ts=ref_ts)

        return feed_items, next_cursor

    async def warm_cache(self) -> None:
        """Warm the Redis cache with top 100 scored videos."""
        if not self.redis:
            return

        now = func.now()
        score_expr = (
            Video.like_count * 10
            + Video.comment_count * 5
            + (1.0 / (func.extract("epoch", now - Video.created_at) / 3600.0 + 2)) * 1000
        ).label("score")

        result = await self.session.execute(
            select(Video, score_expr).order_by(text("score DESC")).limit(self.FEED_CACHE_SIZE),
        )

        pipe = self.redis.pipeline()
        await pipe.delete(self.FEED_CACHE_KEY)
        for row in result.all():
            video, score = row
            await pipe.zadd(self.FEED_CACHE_KEY, {str(video.video_id): float(score)})
        await pipe.execute()

    def _video_to_feed_item(self, video: Video, score: float | None = None) -> FeedItem:
        return FeedItem(
            video_id=str(video.video_id),
            caption=video.caption,
            sound_name=video.sound_name,
            author=UserBriefResponse(
                user_id=video.author_id,
                username=video.author.username if video.author else "",
            ),
            like_count=video.like_count,
            comment_count=video.comment_count,
            created_at=video.created_at.isoformat() if video.created_at else "",
        )
