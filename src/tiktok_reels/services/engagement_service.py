import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tiktok_reels.models.engagement import Like
from tiktok_reels.models.user import User
from tiktok_reels.models.video import Video


class EngagementService:
    """Like/unlike with denormalized counter + Redis counter."""

    def __init__(self, session: AsyncSession, redis_client=None) -> None:
        self.session = session
        self.redis = redis_client

    async def like_video(self, video_id: uuid.UUID, user_id: uuid.UUID) -> tuple[bool, int]:
        """Like a video. Idempotent — returns (liked, like_count).

        Returns (True, count) if new like, (False, count) if already liked.
        """
        # verify entities exist
        video = await self.session.get(Video, video_id)
        if not video:
            raise ValueError("video not found")
        user = await self.session.get(User, user_id)
        if not user:
            raise ValueError("user not found")

        # check if already liked
        existing = await self.session.execute(
            select(Like).where(
                Like.user_id == user_id,
                Like.video_id == video_id,
            ),
        )
        if existing.scalar_one_or_none():
            # already liked — idempotent
            return False, video.like_count

        like = Like(user_id=user_id, video_id=video_id)
        self.session.add(like)

        # increment denormalized counter
        await self.session.execute(
            Video.__table__.update()
            .where(Video.video_id == video_id)
            .values(like_count=Video.like_count + 1),
        )
        await self.session.flush()
        await self.session.refresh(video)

        # Redis counter update
        if self.redis:
            try:
                await self.redis.hincrby(f"counters:{video_id}", "likes", 1)
            except Exception:
                pass

        return True, video.like_count

    async def unlike_video(self, video_id: uuid.UUID, user_id: uuid.UUID) -> tuple[bool, int]:
        """Unlike a video. Idempotent."""
        video = await self.session.get(Video, video_id)
        if not video:
            raise ValueError("video not found")
        user = await self.session.get(User, user_id)
        if not user:
            raise ValueError("user not found")

        existing = await self.session.execute(
            select(Like).where(
                Like.user_id == user_id,
                Like.video_id == video_id,
            ),
        )
        like = existing.scalar_one_or_none()
        if not like:
            return False, video.like_count

        await self.session.delete(like)

        # decrement denormalized counter
        await self.session.execute(
            Video.__table__.update()
            .where(Video.video_id == video_id)
            .values(like_count=Video.like_count - 1),
        )
        await self.session.flush()
        await self.session.refresh(video)

        if self.redis:
            try:
                await self.redis.hincrby(f"counters:{video_id}", "likes", -1)
            except Exception:
                pass

        return True, video.like_count
