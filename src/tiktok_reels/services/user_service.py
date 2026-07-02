import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from tiktok_reels.models.engagement import Follow
from tiktok_reels.models.user import User
from tiktok_reels.models.video import Video
from tiktok_reels.schemas.common import decode_cursor, encode_cursor_datetime
from tiktok_reels.schemas.video import VideoBriefResponse


class UserService:
    """User CRUD, follow/unfollow with counter updates, creator catalog."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_user(self, username: str) -> User:
        """Create a new user. Raises IntegrityError if username taken."""
        user = User(username=username)
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_user(self, user_id: uuid.UUID) -> User | None:
        """Get a user by ID."""
        result = await self.session.execute(
            select(User).where(User.user_id == user_id),
        )
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> User | None:
        """Get a user by username."""
        result = await self.session.execute(
            select(User).where(User.username == username),
        )
        return result.scalar_one_or_none()

    async def follow(self, follower_id: uuid.UUID, followee_id: uuid.UUID) -> bool:
        """Follow a user. Returns True if new follow, False if already following."""
        existing = await self.session.execute(
            select(Follow).where(
                Follow.follower_id == follower_id,
                Follow.followee_id == followee_id,
            ),
        )
        if existing.scalar_one_or_none():
            return False

        follow = Follow(follower_id=follower_id, followee_id=followee_id)
        self.session.add(follow)

        # denormalized counter updates
        await self.session.execute(
            User.__table__.update()
            .where(User.user_id == follower_id)
            .values(following_count=User.following_count + 1),
        )
        await self.session.execute(
            User.__table__.update()
            .where(User.user_id == followee_id)
            .values(follower_count=User.follower_count + 1),
        )
        await self.session.flush()
        return True

    async def unfollow(self, follower_id: uuid.UUID, followee_id: uuid.UUID) -> bool:
        """Unfollow a user. Returns True if was following, False if not."""
        result = await self.session.execute(
            select(Follow).where(
                Follow.follower_id == follower_id,
                Follow.followee_id == followee_id,
            ),
        )
        follow = result.scalar_one_or_none()
        if not follow:
            return False

        await self.session.delete(follow)

        # denormalized counter updates
        await self.session.execute(
            User.__table__.update()
            .where(User.user_id == follower_id)
            .values(following_count=User.following_count - 1),
        )
        await self.session.execute(
            User.__table__.update()
            .where(User.user_id == followee_id)
            .values(follower_count=User.follower_count - 1),
        )
        await self.session.flush()
        return True

    async def get_user_videos(
        self,
        user_id: uuid.UUID,
        cursor: str | None = None,
        limit: int = 20,
    ) -> tuple[list[VideoBriefResponse], str | None]:
        """Get a creator's video catalog, reverse-chronological, cursor paginated."""
        query = (
            select(Video)
            .where(Video.author_id == user_id)
            .order_by(
                Video.created_at.desc(),
                Video.video_id.desc(),
            )
        )

        if cursor:
            try:
                cursor_data = decode_cursor(cursor)
                from datetime import datetime

                cursor_ts = datetime.fromisoformat(cursor_data["created_at"])
                query = query.where(
                    or_(
                        Video.created_at < cursor_ts,
                        (Video.created_at == cursor_ts)
                        & (Video.video_id < uuid.UUID(cursor_data["id"])),
                    ),
                )
            except (ValueError, KeyError) as exc:
                raise ValueError("malformed cursor") from exc

        result = await self.session.execute(query.limit(limit + 1))
        videos = result.scalars().all()

        next_cursor = None
        if len(videos) > limit:
            videos = videos[:limit]
            last = videos[-1]
            next_cursor = encode_cursor_datetime(last.created_at, last.video_id)

        return [VideoBriefResponse.model_validate(v) for v in videos], next_cursor
