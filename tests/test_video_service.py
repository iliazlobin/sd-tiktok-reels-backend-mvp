"""Tests for the VideoService."""

import uuid

import pytest

from tiktok_reels.services.video_service import VideoService


@pytest.fixture
async def video_service(db_session):
    return VideoService(db_session)


class TestCreateVideo:
    async def test_create_video(self, video_service, sample_user_factory):
        user = await sample_user_factory("alice")
        video = await video_service.create_video(
            author_id=user.user_id,
            caption="my first tiktok",
            sound_name="original sound",
            duration_ms=15000,
        )
        assert video.caption == "my first tiktok"
        assert video.author_id == user.user_id
        assert video.like_count == 0
        assert video.comment_count == 0

    async def test_create_video_with_hashtags(self, video_service, sample_user_factory):
        user = await sample_user_factory("alice")
        video = await video_service.create_video(
            author_id=user.user_id,
            caption="dance challenge",
            sound_name="beat",
            duration_ms=10000,
            hashtag_names=["dance", "challenge"],
        )
        hashtags = await video_service.get_video_hashtags(video.video_id)
        assert len(hashtags) == 2
        names = {h.name for h in hashtags}
        assert names == {"dance", "challenge"}

    async def test_hashtag_dedup(self, video_service, sample_user_factory):
        """Same hashtag name reused across videos should share the same Hashtag row."""
        user = await sample_user_factory("alice")
        v1 = await video_service.create_video(
            user.user_id,
            "first",
            "s",
            1000,
            hashtag_names=["trending"],
        )
        v2 = await video_service.create_video(
            user.user_id,
            "second",
            "s",
            1000,
            hashtag_names=["trending"],
        )
        h1 = await video_service.get_video_hashtags(v1.video_id)
        h2 = await video_service.get_video_hashtags(v2.video_id)
        assert h1[0].hashtag_id == h2[0].hashtag_id

    async def test_create_video_unknown_author(self, video_service):
        with pytest.raises(ValueError, match="author not found"):
            await video_service.create_video(
                author_id=uuid.uuid4(),
                caption="test",
                sound_name="s",
                duration_ms=1000,
            )


class TestGetVideo:
    async def test_get_video(self, video_service, sample_video_factory, sample_user_factory):
        user = await sample_user_factory("alice")
        video, _ = await sample_video_factory(author=user, caption="test caption")

        found = await video_service.get_video(video.video_id)
        assert found is not None
        assert found.caption == "test caption"

    async def test_get_video_not_found(self, video_service):
        found = await video_service.get_video(uuid.uuid4())
        assert found is None


class TestSegments:
    async def test_add_segments(self, video_service, sample_video_factory, sample_user_factory):
        user = await sample_user_factory("alice")
        video, _ = await sample_video_factory(author=user)

        count = await video_service.add_segments(
            video.video_id,
            [
                {
                    "quality": "720p",
                    "segment_index": 0,
                    "file_path": "/mock/seg0.ts",
                    "duration_seconds": 5,
                    "size_bytes": 524288,
                },
                {
                    "quality": "540p",
                    "segment_index": 0,
                    "file_path": "/mock/seg1.ts",
                    "duration_seconds": 5,
                    "size_bytes": 393216,
                },
            ],
        )
        assert count == 2

    async def test_add_segments_unknown_video(self, video_service):
        with pytest.raises(ValueError, match="video not found"):
            await video_service.add_segments(uuid.uuid4(), [])
