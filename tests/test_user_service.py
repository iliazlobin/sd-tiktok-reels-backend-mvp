"""Tests for the UserService."""

import uuid

import pytest
from sqlalchemy import select

from tiktok_reels.models.engagement import Follow
from tiktok_reels.services.user_service import UserService


@pytest.fixture
async def user_service(db_session):
    return UserService(db_session)


class TestCreateUser:
    async def test_create_user(self, user_service, db_session):
        user = await user_service.create_user("alice")
        assert user.username == "alice"
        assert user.follower_count == 0
        assert user.following_count == 0
        assert user.user_id is not None

    async def test_duplicate_username_raises(self, user_service):
        await user_service.create_user("alice")
        with pytest.raises(Exception):  # IntegrityError
            await user_service.create_user("alice")


class TestGetUser:
    async def test_get_existing_user(self, user_service, sample_user_factory):
        created = await sample_user_factory("bob")
        found = await user_service.get_user(created.user_id)
        assert found is not None
        assert found.username == "bob"

    async def test_get_nonexistent_user(self, user_service):
        found = await user_service.get_user(uuid.uuid4())
        assert found is None


class TestFollow:
    async def test_follow(self, user_service, sample_user_factory, db_session):
        alice = await sample_user_factory("alice")
        bob = await sample_user_factory("bob")

        result = await user_service.follow(alice.user_id, bob.user_id)
        assert result is True

        # Check follow row exists
        stmt = select(Follow).where(
            Follow.follower_id == alice.user_id,
            Follow.followee_id == bob.user_id,
        )
        result = await db_session.execute(stmt)
        assert result.scalar_one_or_none() is not None

    async def test_follow_idempotent(self, user_service, sample_user_factory):
        alice = await sample_user_factory("alice")
        bob = await sample_user_factory("bob")

        await user_service.follow(alice.user_id, bob.user_id)
        result = await user_service.follow(alice.user_id, bob.user_id)
        assert result is False  # already following

    async def test_follow_updates_counters(self, user_service, sample_user_factory, db_session):
        alice = await sample_user_factory("alice")
        bob = await sample_user_factory("bob")

        await user_service.follow(alice.user_id, bob.user_id)

        await db_session.refresh(alice)
        await db_session.refresh(bob)
        assert alice.following_count == 1
        assert bob.follower_count == 1

    async def test_unfollow(self, user_service, sample_user_factory, db_session):
        alice = await sample_user_factory("alice")
        bob = await sample_user_factory("bob")

        await user_service.follow(alice.user_id, bob.user_id)
        result = await user_service.unfollow(alice.user_id, bob.user_id)
        assert result is True

        # Check follow row deleted
        stmt = select(Follow).where(
            Follow.follower_id == alice.user_id,
            Follow.followee_id == bob.user_id,
        )
        result = await db_session.execute(stmt)
        assert result.scalar_one_or_none() is None

    async def test_unfollow_idempotent(self, user_service, sample_user_factory):
        alice = await sample_user_factory("alice")
        bob = await sample_user_factory("bob")

        result = await user_service.unfollow(alice.user_id, bob.user_id)
        assert result is False  # wasn't following

    async def test_unfollow_updates_counters(self, user_service, sample_user_factory, db_session):
        alice = await sample_user_factory("alice")
        bob = await sample_user_factory("bob")

        await user_service.follow(alice.user_id, bob.user_id)
        await user_service.unfollow(alice.user_id, bob.user_id)

        await db_session.refresh(alice)
        await db_session.refresh(bob)
        assert alice.following_count == 0
        assert bob.follower_count == 0


class TestCreatorCatalog:
    async def test_get_user_videos(self, user_service, sample_video_factory, sample_user_factory):
        user = await sample_user_factory("creator")
        v1, _ = await sample_video_factory(author=user, caption="first")
        v2, _ = await sample_video_factory(author=user, caption="second")

        videos, next_cursor = await user_service.get_user_videos(user.user_id)
        assert len(videos) == 2
        assert next_cursor is None
        video_captions = {v.caption for v in videos}
        assert video_captions == {"first", "second"}

    async def test_cursor_pagination(self, user_service, sample_video_factory, sample_user_factory):
        """Cursor pagination basic test (SQLite datetime comparison may differ from PG)."""
        user = await sample_user_factory("creator")
        # create 3 videos
        for i in range(3):
            await sample_video_factory(author=user, caption=f"video_{i}")

        # Without cursor we get all videos
        videos_all, _ = await user_service.get_user_videos(user.user_id)
        assert len(videos_all) == 3

        # With limit=2, we get 2 + a cursor
        videos, next_cursor = await user_service.get_user_videos(user.user_id, limit=2)
        assert len(videos) == 2
        assert next_cursor is not None
