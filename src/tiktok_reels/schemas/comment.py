import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from tiktok_reels.schemas.common import PaginatedResponse
from tiktok_reels.schemas.user import UserBriefResponse


class CommentCreate(BaseModel):
    user_id: uuid.UUID
    text: str = Field(..., min_length=1)


class CommentResponse(BaseModel):
    comment_id: uuid.UUID
    video_id: uuid.UUID
    user_id: uuid.UUID
    text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CommentItem(BaseModel):
    comment_id: uuid.UUID
    text: str
    user: UserBriefResponse
    created_at: datetime


class CommentListResponse(PaginatedResponse):
    comments: list[CommentItem]
