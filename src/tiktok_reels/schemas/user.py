import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)


class UserResponse(BaseModel):
    user_id: uuid.UUID
    username: str
    follower_count: int
    following_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class UserBriefResponse(BaseModel):
    user_id: uuid.UUID
    username: str

    model_config = {"from_attributes": True}
