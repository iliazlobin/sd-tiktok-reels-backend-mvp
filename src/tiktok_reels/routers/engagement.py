import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from tiktok_reels.database import get_session
from tiktok_reels.redis import get_redis
from tiktok_reels.schemas.engagement import LikeRequest, LikeResponse
from tiktok_reels.services.engagement_service import EngagementService

router = APIRouter(tags=["engagement"])


@router.post("/api/v1/videos/{video_id}/like")
async def like_video(
    video_id: uuid.UUID,
    body: LikeRequest,
    session: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
) -> LikeResponse:
    service = EngagementService(session, redis_client=redis)
    try:
        liked, count = await service.like_video(video_id, body.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return LikeResponse(liked=True, like_count=count)


@router.delete("/api/v1/videos/{video_id}/like")
async def unlike_video(
    video_id: uuid.UUID,
    body: LikeRequest,
    session: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
) -> LikeResponse:
    service = EngagementService(session, redis_client=redis)
    try:
        unliked, count = await service.unlike_video(video_id, body.user_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await session.commit()
    return LikeResponse(liked=False, like_count=count)
