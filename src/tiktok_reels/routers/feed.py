from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from tiktok_reels.database import get_session
from tiktok_reels.redis import get_redis
from tiktok_reels.schemas.feed import FeedResponse
from tiktok_reels.services.feed_service import FeedService

router = APIRouter(prefix="/api/v1/feed", tags=["feed"])


@router.get("")
async def get_feed(
    cursor: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
    redis=Depends(get_redis),
) -> FeedResponse:
    service = FeedService(session, redis_client=redis)
    try:
        videos, next_cursor = await service.get_feed(cursor=cursor)
    except ValueError:
        raise HTTPException(status_code=400, detail="malformed cursor")

    return FeedResponse(videos=videos, next_cursor=next_cursor)
