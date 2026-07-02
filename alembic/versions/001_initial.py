"""Initial migration: create all TikTok/Reels tables.

Revision ID: 001
Revises: None
Create Date: 2026-07-01

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # --- users ---
    op.create_table(
        "users",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("username", sa.String(50), unique=True, nullable=False, index=True),
        sa.Column("follower_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("following_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # --- hashtags ---
    op.create_table(
        "hashtags",
        sa.Column(
            "hashtag_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(100), unique=True, nullable=False, index=True),
    )

    # --- videos ---
    op.create_table(
        "videos",
        sa.Column(
            "video_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "author_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id"),
            nullable=False,
            index=True,
        ),
        sa.Column("caption", sa.Text(), nullable=False),
        sa.Column(
            "sound_name", sa.String(255), nullable=False, server_default=sa.text("'original sound'")
        ),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("like_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("comment_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("share_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # --- video_hashtags ---
    op.create_table(
        "video_hashtags",
        sa.Column(
            "video_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("videos.video_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "hashtag_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hashtags.hashtag_id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # --- comments ---
    op.create_table(
        "comments",
        sa.Column(
            "comment_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "video_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("videos.video_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # --- likes ---
    op.create_table(
        "likes",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "video_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("videos.video_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("user_id", "video_id", name="uq_like_user_video"),
    )

    # --- follows ---
    op.create_table(
        "follows",
        sa.Column(
            "follower_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "followee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.user_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("follower_id", "followee_id", name="uq_follow_follower_followee"),
    )

    # --- video_segments ---
    op.create_table(
        "video_segments",
        sa.Column(
            "segment_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "video_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("videos.video_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("quality", sa.String(10), nullable=False),
        sa.Column("segment_index", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "video_id", "quality", "segment_index", name="uq_segment_video_quality_index"
        ),
    )

    # --- FTS indexes ---
    op.execute(
        "CREATE INDEX ix_videos_fts ON videos "
        "USING GIN (to_tsvector('english', caption || ' ' || sound_name))"
    )
    op.execute(
        "CREATE INDEX ix_hashtags_fts ON hashtags " "USING GIN (to_tsvector('english', name))"
    )


def downgrade() -> None:
    op.drop_table("video_segments")
    op.drop_table("follows")
    op.drop_table("likes")
    op.drop_table("comments")
    op.drop_table("video_hashtags")
    op.drop_table("videos")
    op.drop_table("hashtags")
    op.drop_table("users")
