import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from tiktok_reels.database import get_session
from tiktok_reels.schemas.video import (
    HashtagResponse,
    SegmentCreate,
    VideoCreate,
    VideoDetailResponse,
    VideoResponse,
)
from tiktok_reels.services.video_service import VideoService

router = APIRouter(prefix="/api/v1/videos", tags=["videos"])


@router.post("", status_code=201)
async def create_video(
    body: VideoCreate,
    session: AsyncSession = Depends(get_session),
) -> VideoResponse:
    service = VideoService(session)
    try:
        video = await service.create_video(
            author_id=body.author_id,
            caption=body.caption,
            sound_name=body.sound_name,
            duration_ms=body.duration_ms,
            hashtag_names=body.hashtags,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    hashtags = await service.get_video_hashtags(video.video_id)
    # Reload with eager relations
    await session.refresh(video)

    return VideoResponse(
        video_id=video.video_id,
        author_id=video.author_id,
        caption=video.caption,
        sound_name=video.sound_name,
        duration_ms=video.duration_ms,
        like_count=video.like_count,
        comment_count=video.comment_count,
        share_count=video.share_count,
        hashtags=[HashtagResponse.model_validate(h) for h in hashtags],
        created_at=video.created_at,
    )


@router.get("/{video_id}")
async def get_video_detail(
    video_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> VideoDetailResponse:
    service = VideoService(session)
    video = await service.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="video not found")

    # eager load author
    from tiktok_reels.models.user import User

    author = await session.get(User, video.author_id)

    hashtags = await service.get_video_hashtags(video_id)

    from tiktok_reels.schemas.user import UserBriefResponse

    return VideoDetailResponse(
        video_id=video.video_id,
        caption=video.caption,
        sound_name=video.sound_name,
        duration_ms=video.duration_ms,
        like_count=video.like_count,
        comment_count=video.comment_count,
        share_count=video.share_count,
        author=UserBriefResponse(user_id=author.user_id, username=author.username)
        if author
        else UserBriefResponse(user_id=video.author_id, username="unknown"),
        hashtags=[HashtagResponse.model_validate(h) for h in hashtags],
        created_at=video.created_at,
    )


@router.post("/{video_id}/segments", status_code=201)
async def add_segments(
    video_id: uuid.UUID,
    body: SegmentCreate,
    session: AsyncSession = Depends(get_session),
) -> dict:
    service = VideoService(session)
    try:
        count = await service.add_segments(
            video_id,
            [s.model_dump() for s in body.segments],
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"video_id": str(video_id), "segment_count": count}
