import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tiktok_reels.models.hashtag import Hashtag, VideoHashtag
from tiktok_reels.models.segment import VideoSegment
from tiktok_reels.models.user import User
from tiktok_reels.models.video import Video
from tiktok_reels.schemas.video import HashtagResponse


class VideoService:
    """Video create with hashtag upsert, detail with author/engagement."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_video(
        self,
        author_id: uuid.UUID,
        caption: str,
        sound_name: str,
        duration_ms: int,
        hashtag_names: list[str] | None = None,
    ) -> Video:
        """Create a video with optional hashtag upsert."""
        # verify author exists
        author = await self.session.get(User, author_id)
        if not author:
            raise ValueError("author not found")

        video = Video(
            author_id=author_id,
            caption=caption,
            sound_name=sound_name,
            duration_ms=duration_ms,
        )
        self.session.add(video)
        await self.session.flush()

        # upsert hashtags
        if hashtag_names:
            for name in hashtag_names:
                hashtag = await self._get_or_create_hashtag(name)
                vh = VideoHashtag(video_id=video.video_id, hashtag_id=hashtag.hashtag_id)
                self.session.add(vh)
            await self.session.flush()

        return video

    async def get_video(self, video_id: uuid.UUID) -> Video | None:
        """Get a video by ID (eager load author and hashtags)."""
        result = await self.session.execute(
            select(Video).where(Video.video_id == video_id),
        )
        return result.scalar_one_or_none()

    async def get_video_hashtags(self, video_id: uuid.UUID) -> list[Hashtag]:
        """Get hashtags for a video."""
        result = await self.session.execute(
            select(Hashtag)
            .join(VideoHashtag, VideoHashtag.hashtag_id == Hashtag.hashtag_id)
            .where(VideoHashtag.video_id == video_id),
        )
        return list(result.scalars().all())

    async def add_segments(
        self,
        video_id: uuid.UUID,
        segments_data: list[dict],
    ) -> int:
        """Add video segments in bulk (upsert by video_id, quality, segment_index)."""
        video = await self.session.get(Video, video_id)
        if not video:
            raise ValueError("video not found")

        count = 0
        for seg in segments_data:
            existing = await self.session.execute(
                select(VideoSegment).where(
                    VideoSegment.video_id == video_id,
                    VideoSegment.quality == seg["quality"],
                    VideoSegment.segment_index == seg["segment_index"],
                ),
            )
            existing_seg = existing.scalar_one_or_none()
            if existing_seg:
                # update
                existing_seg.file_path = seg["file_path"]
                existing_seg.duration_seconds = seg["duration_seconds"]
                existing_seg.size_bytes = seg["size_bytes"]
            else:
                new_seg = VideoSegment(
                    video_id=video_id,
                    quality=seg["quality"],
                    segment_index=seg["segment_index"],
                    file_path=seg["file_path"],
                    duration_seconds=seg["duration_seconds"],
                    size_bytes=seg["size_bytes"],
                )
                self.session.add(new_seg)
            count += 1

        await self.session.flush()
        return count

    async def _get_or_create_hashtag(self, name: str) -> Hashtag:
        """Look up or create a hashtag by name."""
        result = await self.session.execute(
            select(Hashtag).where(Hashtag.name == name),
        )
        hashtag = result.scalar_one_or_none()
        if not hashtag:
            hashtag = Hashtag(name=name)
            self.session.add(hashtag)
            await self.session.flush()
        return hashtag

    @staticmethod
    def hashtags_to_responses(hashtags: list[Hashtag]) -> list[HashtagResponse]:
        return [HashtagResponse.model_validate(h) for h in hashtags]
