import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tiktok_reels.database import get_session
from tiktok_reels.schemas.engagement import FollowResponse
from tiktok_reels.schemas.user import UserCreate, UserResponse
from tiktok_reels.services.user_service import UserService

router = APIRouter(prefix="/api/v1/users", tags=["users"])


@router.post("", status_code=201)
async def create_user(
    body: UserCreate,
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    service = UserService(session)
    try:
        user = await service.create_user(body.username)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="username already taken") from exc
    return UserResponse.model_validate(user)


@router.get("/{user_id}")
async def get_user(
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> UserResponse:
    service = UserService(session)
    user = await service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return UserResponse.model_validate(user)


@router.get("/{user_id}/videos")
async def get_user_videos(
    user_id: uuid.UUID,
    cursor: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> dict:
    service = UserService(session)
    user = await service.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    try:
        videos, next_cursor = await service.get_user_videos(user_id, cursor=cursor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="malformed cursor") from exc
    return {
        "videos": [v.model_dump() for v in videos],
        "next_cursor": next_cursor,
    }


@router.post("/{followee_id}/follow")
async def follow_user(
    followee_id: uuid.UUID,
    follower_id: uuid.UUID = Query(...),
    session: AsyncSession = Depends(get_session),
) -> FollowResponse:
    if follower_id == followee_id:
        raise HTTPException(status_code=422, detail="cannot follow yourself")
    service = UserService(session)
    followee = await service.get_user(followee_id)
    if not followee:
        raise HTTPException(status_code=404, detail="followee not found")
    follower = await service.get_user(follower_id)
    if not follower:
        raise HTTPException(status_code=404, detail="follower not found")
    await service.follow(follower_id, followee_id)
    return FollowResponse(status="following")


@router.delete("/{followee_id}/follow")
async def unfollow_user(
    followee_id: uuid.UUID,
    follower_id: uuid.UUID = Query(...),
    session: AsyncSession = Depends(get_session),
) -> FollowResponse:
    if follower_id == followee_id:
        raise HTTPException(status_code=422, detail="cannot unfollow yourself")
    service = UserService(session)
    followee = await service.get_user(followee_id)
    if not followee:
        raise HTTPException(status_code=404, detail="followee not found")
    follower = await service.get_user(follower_id)
    if not follower:
        raise HTTPException(status_code=404, detail="follower not found")
    await service.unfollow(follower_id, followee_id)
    return FollowResponse(status="unfollowed")
