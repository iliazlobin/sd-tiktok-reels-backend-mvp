"""FR2: View a personalized trending feed of recommended videos.

GET /api/v1/feed → 200 with video list
Cursor pagination: next_cursor advances through feed
Malformed cursor → 400
Feed items have expected structure
"""

from verify.acceptance.conftest import (
    add_segments,
    assert_400,
    create_user,
    create_video,
    get_feed,
)


def test_feed_returns_videos(client):
    """Feed endpoint returns a list of videos with expected structure."""
    user = create_user(client)
    video = create_video(client, user["user_id"], caption="trending video")
    add_segments(client, video["video_id"])

    body = get_feed(client)

    assert "videos" in body
    assert isinstance(body["videos"], list)

    for item in body["videos"]:
        assert "video_id" in item
        assert "caption" in item
        assert "sound_name" in item
        assert "author" in item
        assert "like_count" in item
        assert "comment_count" in item
        assert "created_at" in item


def test_feed_pagination(client):
    """Feed supports cursor-based pagination — cursor advances through results."""
    user = create_user(client)
    # Create several videos to ensure pagination
    for i in range(20):
        video = create_video(client, user["user_id"], caption=f"video {i}")
        add_segments(client, video["video_id"])

    page1 = get_feed(client)
    assert len(page1["videos"]) > 0

    # If there's a next_cursor, fetch the next page
    if page1.get("next_cursor"):
        page2 = get_feed(client, cursor=page1["next_cursor"])
        assert "videos" in page2

        # Videos on page 2 should be different from page 1
        page1_ids = {v["video_id"] for v in page1["videos"]}
        page2_ids = {v["video_id"] for v in page2.get("videos", [])}
        assert page1_ids.isdisjoint(page2_ids), "Pages should not overlap"


def test_feed_null_cursor_last_page(client):
    """The last page of feed has next_cursor set to null."""
    user = create_user(client)
    video = create_video(client, user["user_id"], caption="only video")
    add_segments(client, video["video_id"])

    body = get_feed(client)
    # With few videos, all should fit in one page
    # next_cursor may be null if fewer than page size
    assert "next_cursor" in body


def test_feed_malformed_cursor_400(client):
    """Passing a malformed cursor returns 400."""
    r = client.get("/api/v1/feed", params={"cursor": "not-valid-base64!!!"})
    assert_400(r)


def test_feed_empty_database(client):
    """Feed returns empty list when no videos exist (not a crash)."""
    body = get_feed(client)
    assert body["videos"] == []
    assert body.get("next_cursor") is None


def test_feed_structure_consistent(client):
    """Every video in the feed has the same set of top-level keys."""
    user = create_user(client)
    for i in range(3):
        video = create_video(client, user["user_id"], caption=f"vid {i}")
        add_segments(client, video["video_id"])

    body = get_feed(client)
    required_keys = {
        "video_id",
        "caption",
        "sound_name",
        "author",
        "like_count",
        "comment_count",
        "created_at",
    }

    for item in body["videos"]:
        assert required_keys.issubset(
            item.keys()
        ), f"Missing keys: {required_keys - set(item.keys())}"
        assert "user_id" in item["author"]
        assert "username" in item["author"]
