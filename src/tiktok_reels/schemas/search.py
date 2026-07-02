from pydantic import BaseModel, Field

from tiktok_reels.schemas.common import PaginatedResponse


class SearchResult(BaseModel):
    type: str = Field(..., description="One of: video, hashtag, user")
    video_id: str | None = None
    caption: str | None = None
    hashtag_id: str | None = None
    name: str | None = None
    user_id: str | None = None
    username: str | None = None
    like_count: int | None = None
    created_at: str | None = None


class SearchResponse(PaginatedResponse):
    results: list[SearchResult]
