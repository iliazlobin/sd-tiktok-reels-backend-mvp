import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tiktok_reels.models.base import Base


class VideoSegment(Base):
    __tablename__ = "video_segments"
    __table_args__ = (
        UniqueConstraint(
            "video_id", "quality", "segment_index", name="uq_segment_video_quality_index"
        ),
    )

    segment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("videos.video_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quality: Mapped[str] = mapped_column(String(10), nullable=False)
    segment_index: Mapped[int] = mapped_column(Integer, nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    # relationships
    video = relationship("Video", back_populates="segments")
