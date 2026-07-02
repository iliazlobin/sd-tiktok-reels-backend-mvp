"""Tests for the EngagementService."""

import uuid

import pytest

from tiktok_reels.services.engagement_service import EngagementService


@pytest.fixture
async def engagement_service(db_session):
    return EngagementService(db_session)


class TestLikeVideo:
    async def test_like(self, engagement_service, sample_video_factory, sample_user_factory):
        user = await sample_user_factory("alice")
        video, author = await sample_video_factory(author=user)
        liked, count = await engagement_service.like_video(video.video_id, user.user_id)
        assert liked is True
        assert count == 1

    async def test_like_idempotent(
        self, engagement_service, sample_video_factory, sample_user_factory
    ):
        user = await sample_user_factory("alice")
        video, _ = await sample_video_factory(author=user)
        await engagement_service.like_video(video.video_id, user.user_id)
        liked, count = await engagement_service.like_video(video.video_id, user.user_id)
        assert liked is False  # already liked
        assert count == 1  # count stays at 1

    async def test_unlike(self, engagement_service, sample_video_factory, sample_user_factory):
        user = await sample_user_factory("alice")
        video, _ = await sample_video_factory(author=user)
        await engagement_service.like_video(video.video_id, user.user_id)
        unliked, count = await engagement_service.unlike_video(video.video_id, user.user_id)
        assert unliked is True
        assert count == 0

    async def test_unlike_idempotent(
        self, engagement_service, sample_video_factory, sample_user_factory
    ):
        user = await sample_user_factory("alice")
        video, _ = await sample_video_factory(author=user)
        unliked, count = await engagement_service.unlike_video(video.video_id, user.user_id)
        assert unliked is False

    async def test_like_unknown_video(self, engagement_service, sample_user_factory):
        user = await sample_user_factory("alice")
        with pytest.raises(ValueError, match="video not found"):
            await engagement_service.like_video(uuid.uuid4(), user.user_id)

    async def test_like_unknown_user(
        self, engagement_service, sample_video_factory, sample_user_factory
    ):
        user = await sample_user_factory("alice")
        video, _ = await sample_video_factory(author=user)
        with pytest.raises(ValueError, match="user not found"):
            await engagement_service.like_video(video.video_id, uuid.uuid4())
