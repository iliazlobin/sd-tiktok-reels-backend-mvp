from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from tiktok_reels.database import get_session
from tiktok_reels.schemas.search import SearchResponse
from tiktok_reels.services.search_service import SearchService

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("")
async def search(
    q: str = Query(default=""),
    type: str = Query(default="all", alias="type"),
    cursor: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> SearchResponse:
    if not q or not q.strip():
        return SearchResponse(results=[], next_cursor=None)

    service = SearchService(session)
    try:
        results, next_cursor = await service.search(q, search_type=type, cursor=cursor)
    except ValueError:
        raise HTTPException(status_code=400, detail="malformed cursor")

    return SearchResponse(results=results, next_cursor=next_cursor)
