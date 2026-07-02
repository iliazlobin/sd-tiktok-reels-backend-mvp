"""Tests for the CommentService."""

import uuid

import pytest

from tiktok_reels.services.comment_service import CommentService


@pytest.fixture
async def comment_service(db_session):
    return CommentService(db_session)


class TestCreateComment:
    async def test_create_comment(self, comment_service, sample_video_factory, sample_user_factory):
        user = await sample_user_factory("alice")
        video, _ = await sample_video_factory(author=user)
        comment = await comment_service.create_comment(
            video.video_id,
            user.user_id,
            "nice video!",
        )
        assert comment.text == "nice video!"
        assert comment.comment_id is not None

    async def test_create_comment_unknown_video(self, comment_service, sample_user_factory):
        user = await sample_user_factory("alice")
        with pytest.raises(ValueError, match="video not found"):
            await comment_service.create_comment(uuid.uuid4(), user.user_id, "hello")

    async def test_create_comment_unknown_user(
        self, comment_service, sample_video_factory, sample_user_factory
    ):
        user = await sample_user_factory("alice")
        video, _ = await sample_video_factory(author=user)
        with pytest.raises(ValueError, match="user not found"):
            await comment_service.create_comment(video.video_id, uuid.uuid4(), "hello")


class TestListComments:
    async def test_list_comments(self, comment_service, sample_video_factory, sample_user_factory):
        user = await sample_user_factory("alice")
        video, _ = await sample_video_factory(author=user)
        await comment_service.create_comment(video.video_id, user.user_id, "first")
        await comment_service.create_comment(video.video_id, user.user_id, "second")

        comments, next_cursor = await comment_service.get_comments(video.video_id)
        assert len(comments) == 2
        texts = {c.text for c in comments}
        assert texts == {"first", "second"}

    async def test_comments_cursor(
        self, comment_service, sample_video_factory, sample_user_factory
    ):
        user = await sample_user_factory("alice")
        video, _ = await sample_video_factory(author=user)
        # Create more than page size
        for i in range(25):
            await comment_service.create_comment(video.video_id, user.user_id, f"comment_{i}")

        comments, next_cursor = await comment_service.get_comments(video.video_id)
        assert len(comments) == 20
        assert next_cursor is not None

    async def test_list_comments_unknown_video(self, comment_service):
        with pytest.raises(ValueError, match="video not found"):
            await comment_service.get_comments(uuid.uuid4())
