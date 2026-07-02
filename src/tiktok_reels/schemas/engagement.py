import uuid

from pydantic import BaseModel


class LikeRequest(BaseModel):
    user_id: uuid.UUID


class LikeResponse(BaseModel):
    liked: bool
    like_count: int


class FollowResponse(BaseModel):
    status: str
