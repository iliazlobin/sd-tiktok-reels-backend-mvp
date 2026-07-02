import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from tiktok_reels.database import get_session
from tiktok_reels.schemas.comment import (
    CommentCreate,
    CommentListResponse,
    CommentResponse,
)
from tiktok_reels.services.comment_service import CommentService

router = APIRouter(tags=["comments"])


@router.post("/api/v1/videos/{video_id}/comments", status_code=201)
async def create_comment(
    video_id: uuid.UUID,
    body: CommentCreate,
    session: AsyncSession = Depends(get_session),
) -> CommentResponse:
    service = CommentService(session)
    try:
        comment = await service.create_comment(video_id, body.user_id, body.text)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return CommentResponse.model_validate(comment)


@router.get("/api/v1/videos/{video_id}/comments")
async def list_comments(
    video_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> CommentListResponse:
    service = CommentService(session)
    try:
        comments, next_cursor = await service.get_comments(video_id, cursor=cursor)
    except ValueError:
        raise HTTPException(status_code=400, detail="malformed cursor")

    return CommentListResponse(comments=comments, next_cursor=next_cursor)
