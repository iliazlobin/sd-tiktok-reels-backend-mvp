from pydantic import BaseModel

from tiktok_reels.schemas.common import PaginatedResponse
from tiktok_reels.schemas.user import UserBriefResponse


class FeedItem(BaseModel):
    video_id: str
    caption: str
    sound_name: str
    author: UserBriefResponse
    like_count: int
    comment_count: int
    created_at: str


class FeedResponse(PaginatedResponse):
    videos: list[FeedItem]
