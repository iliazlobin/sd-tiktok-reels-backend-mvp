import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tiktok_reels.models.segment import VideoSegment
from tiktok_reels.models.video import Video


class StreamingService:
    """Manifest XML generation, segment file lookup and byte serving."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_video_segments(self, video_id: uuid.UUID) -> list[VideoSegment]:
        """Get all segments for a video, ordered by quality and index."""
        result = await self.session.execute(
            select(VideoSegment)
            .where(VideoSegment.video_id == video_id)
            .order_by(VideoSegment.quality, VideoSegment.segment_index),
        )
        return list(result.scalars().all())

    async def get_segment(self, segment_id: uuid.UUID) -> VideoSegment | None:
        """Get a single segment by ID."""
        return await self.session.get(VideoSegment, segment_id)

    async def get_video(self, video_id: uuid.UUID) -> Video | None:
        """Get video by ID."""
        return await self.session.get(Video, video_id)

    def build_manifest_xml(self, video_id: str, segments: list[VideoSegment]) -> str:
        """Build an MPEG-DASH MPD manifest XML string."""
        quality_groups: dict[str, list[VideoSegment]] = {}
        for seg in segments:
            quality_groups.setdefault(seg.quality, []).append(seg)

        lines = [
            '<?xml version="1.0" encoding="utf-8"?>',
            (
                f'<MPD xmlns="urn:mpeg:dash:schema:mpd:2011"'
                f' minBufferTime="PT2S"'
                f' profiles="urn:mpeg:dash:profile:isoff-live:2011"'
                f' type="static"'
                f' publishTime="{uuid.uuid4().hex[:8]}">'
            ),
            f'  <Period id="1" duration="PT{(sum(s.duration_seconds for s in segments) // 1)}S">',
        ]

        for quality, segs in quality_groups.items():
            bandwidth = {"720p": 2000000, "540p": 1000000, "360p": 500000, "1080p": 4000000}.get(
                quality, 1000000
            )
            lines.append(
                f'    <AdaptationSet mimeType="video/mp2t"'
                f' contentType="video" bandwidth="{bandwidth}">'
            )
            lines.append(f'      <Representation id="{quality}" bandwidth="{bandwidth}">')
            lines.append(
                f'        <SegmentList duration="{segs[0].duration_seconds if segs else 5}">'
            )
            for seg in segs:
                lines.append(f'          <SegmentURL media="/api/v1/segments/{seg.segment_id}" />')
            lines.append("        </SegmentList>")
            lines.append("      </Representation>")
            lines.append("    </AdaptationSet>")

        lines.append("  </Period>")
        lines.append("</MPD>")

        return "\n".join(lines)
