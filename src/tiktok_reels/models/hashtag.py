import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tiktok_reels.models.base import Base


class Hashtag(Base):
    __tablename__ = "hashtags"

    hashtag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    # relationships
    videos = relationship("VideoHashtag", back_populates="hashtag", cascade="all, delete-orphan")


class VideoHashtag(Base):
    __tablename__ = "video_hashtags"

    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("videos.video_id", ondelete="CASCADE"),
        primary_key=True,
    )
    hashtag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hashtags.hashtag_id", ondelete="CASCADE"),
        primary_key=True,
    )

    # relationships
    video = relationship("Video", back_populates="hashtags")
    hashtag = relationship("Hashtag", back_populates="videos")
