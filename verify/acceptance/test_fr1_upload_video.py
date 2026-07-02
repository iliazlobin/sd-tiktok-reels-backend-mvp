"""FR1: Upload and publish a short-form video with caption and sound.

POST /api/v1/videos → 201 with video_id, caption, hashtags
GET /api/v1/videos/{id} → 200 with author, hashtags, counts
Unknown author → 404
Empty caption → 422
"""

from verify.acceptance.conftest import (
    assert_404,
    assert_422,
    create_user,
    create_video,
    get_video_detail,
)


def test_create_video_201(client):
    """Creating a valid video returns 201 with the video data."""
    user = create_user(client)
    body = create_video(client, user["user_id"], caption="my first tiktok")

    assert body["caption"] == "my first tiktok"
    assert body["author_id"] == user["user_id"]
    assert body["sound_name"] == "original sound"
    assert body["duration_ms"] == 15000
    assert body["like_count"] == 0
    assert body["comment_count"] == 0
    assert "video_id" in body
    assert "created_at" in body


def test_create_video_with_hashtags(client):
    """Creating a video with hashtags extracts and returns them."""
    user = create_user(client)
    body = create_video(
        client,
        user["user_id"],
        caption="dance challenge",
        hashtags=["dance", "challenge", "viral"],
    )

    assert "hashtags" in body
    hashtag_names = {h["name"] for h in body["hashtags"]}
    assert hashtag_names == {"dance", "challenge", "viral"}

    # Hashtags should have IDs
    for h in body["hashtags"]:
        assert "hashtag_id" in h


def test_hashtag_deduplication(client):
    """Creating videos with the same hashtag reuses existing hashtags."""
    user = create_user(client)
    v1 = create_video(client, user["user_id"], caption="first", hashtags=["trending"])
    v2 = create_video(client, user["user_id"], caption="second", hashtags=["trending"])

    h1_ids = {h["hashtag_id"] for h in v1["hashtags"]}
    h2_ids = {h["hashtag_id"] for h in v2["hashtags"]}
    # Same hashtag name should map to same ID
    assert h1_ids == h2_ids


def test_get_video_detail(client):
    """Video detail returns full metadata with author and hashtags."""
    user = create_user(client)
    video = create_video(
        client,
        user["user_id"],
        caption="check this out",
        sound_name="cool beat",
        hashtags=["music"],
    )

    detail = get_video_detail(client, video["video_id"])

    assert detail["video_id"] == video["video_id"]
    assert detail["caption"] == "check this out"
    assert detail["sound_name"] == "cool beat"
    assert "author" in detail
    assert detail["author"]["user_id"] == user["user_id"]
    assert detail["author"]["username"] == user["username"]
    assert "hashtags" in detail
    assert len(detail["hashtags"]) == 1
    assert detail["hashtags"][0]["name"] == "music"


def test_create_video_unknown_author_404(client):
    """Creating a video for a non-existent author returns 404."""
    fake_user_id = "00000000-0000-0000-0000-000000000000"
    r = client.post(
        "/api/v1/videos",
        json={
            "author_id": fake_user_id,
            "caption": "ghost video",
            "sound_name": "ghost sound",
            "duration_ms": 10000,
        },
    )
    assert_404(r)


def test_create_video_empty_caption_422(client):
    """Creating a video with an empty caption returns 422."""
    user = create_user(client)
    r = client.post(
        "/api/v1/videos",
        json={
            "author_id": user["user_id"],
            "caption": "",
            "sound_name": "sound",
            "duration_ms": 10000,
        },
    )
    assert_422(r)


def test_create_video_negative_duration_422(client):
    """Creating a video with zero or negative duration returns 422."""
    user = create_user(client)
    r = client.post(
        "/api/v1/videos",
        json={
            "author_id": user["user_id"],
            "caption": "bad duration",
            "sound_name": "sound",
            "duration_ms": 0,
        },
    )
    assert_422(r)


def test_get_video_unknown_404(client):
    """Fetching a non-existent video returns 404."""
    fake_video_id = "00000000-0000-0000-0000-000000000000"
    r = client.get(f"/api/v1/videos/{fake_video_id}")
    assert_404(r)


def test_create_video_without_hashtags(client):
    """Creating a video without hashtags returns an empty hashtags list."""
    user = create_user(client)
    body = create_video(client, user["user_id"], caption="no tags here")
    assert body["hashtags"] == []
