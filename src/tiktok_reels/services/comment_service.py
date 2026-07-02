import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from tiktok_reels.models.comment import Comment
from tiktok_reels.models.user import User
from tiktok_reels.models.video import Video
from tiktok_reels.schemas.comment import CommentItem, UserBriefResponse
from tiktok_reels.schemas.common import decode_cursor, encode_cursor_datetime


class CommentService:
    """Comment create, paginated list."""

    PAGE_SIZE = 20

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_comment(
        self,
        video_id: uuid.UUID,
        user_id: uuid.UUID,
        text: str,
    ) -> Comment:
        """Create a comment and increment comment_count on the video."""
        # verify video and user exist
        video = await self.session.get(Video, video_id)
        if not video:
            raise ValueError("video not found")
        user = await self.session.get(User, user_id)
        if not user:
            raise ValueError("user not found")

        comment = Comment(video_id=video_id, user_id=user_id, text=text)
        self.session.add(comment)

        # increment denormalized counter
        await self.session.execute(
            Video.__table__.update()
            .where(Video.video_id == video_id)
            .values(comment_count=Video.comment_count + 1),
        )
        await self.session.flush()
        return comment

    async def get_comments(
        self,
        video_id: uuid.UUID,
        cursor: str | None = None,
    ) -> tuple[list[CommentItem], str | None]:
        """List comments for a video, oldest-first, cursor paginated."""
        # verify video exists
        video = await self.session.get(Video, video_id)
        if not video:
            raise ValueError("video not found")

        query = (
            select(Comment)
            .options(selectinload(Comment.user))
            .where(Comment.video_id == video_id)
            .order_by(Comment.created_at.asc(), Comment.comment_id.asc())
        )

        if cursor:
            try:
                cursor_data = decode_cursor(cursor)
                from datetime import datetime

                cursor_ts = datetime.fromisoformat(cursor_data["created_at"])
                query = query.where(
                    or_(
                        Comment.created_at > cursor_ts,
                        (Comment.created_at == cursor_ts)
                        & (Comment.comment_id > uuid.UUID(cursor_data["id"])),
                    ),
                )
            except (ValueError, KeyError) as exc:
                raise ValueError("malformed cursor") from exc

        result = await self.session.execute(query.limit(self.PAGE_SIZE + 1))
        comments = result.scalars().all()

        next_cursor = None
        if len(comments) > self.PAGE_SIZE:
            comments = comments[: self.PAGE_SIZE]
            last = comments[-1]
            next_cursor = encode_cursor_datetime(last.created_at, last.comment_id)

        items = []
        for c in comments:
            items.append(
                CommentItem(
                    comment_id=c.comment_id,
                    text=c.text,
                    user=UserBriefResponse(
                        user_id=c.user.user_id,
                        username=c.user.username,
                    ),
                    created_at=c.created_at,
                )
            )

        return items, next_cursor
