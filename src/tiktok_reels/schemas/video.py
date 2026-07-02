import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from tiktok_reels.schemas.user import UserBriefResponse


class HashtagResponse(BaseModel):
    hashtag_id: uuid.UUID
    name: str

    model_config = {"from_attributes": True}


class VideoCreate(BaseModel):
    author_id: uuid.UUID
    caption: str = Field(..., min_length=1)
    sound_name: str = "original sound"
    duration_ms: int = Field(..., gt=0)
    hashtags: list[str] | None = None


class VideoResponse(BaseModel):
    video_id: uuid.UUID
    author_id: uuid.UUID
    caption: str
    sound_name: str
    duration_ms: int
    like_count: int
    comment_count: int
    share_count: int
    hashtags: list[HashtagResponse]
    created_at: datetime

    model_config = {"from_attributes": True}


class VideoDetailResponse(BaseModel):
    video_id: uuid.UUID
    caption: str
    sound_name: str
    duration_ms: int
    like_count: int
    comment_count: int
    share_count: int
    author: UserBriefResponse
    hashtags: list[HashtagResponse]
    created_at: datetime

    model_config = {"from_attributes": True}


class VideoBriefResponse(BaseModel):
    video_id: uuid.UUID
    caption: str
    like_count: int
    comment_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class SegmentCreateItem(BaseModel):
    quality: str = Field(..., pattern=r"^(360p|540p|720p|1080p)$")
    segment_index: int = Field(..., ge=0)
    file_path: str
    duration_seconds: int = Field(..., gt=0)
    size_bytes: int = Field(..., gt=0)


class SegmentCreate(BaseModel):
    segments: list[SegmentCreateItem] = Field(..., min_length=1)


class SegmentResponse(BaseModel):
    segment_id: uuid.UUID
    quality: str
    segment_index: int
    file_path: str
    duration_seconds: int
    size_bytes: int

    model_config = {"from_attributes": True}
