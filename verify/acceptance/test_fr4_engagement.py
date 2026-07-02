"""FR4: Like, comment on, and share videos.

POST /api/v1/videos/{id}/like → 200 {liked: true, like_count: N}
DELETE /api/v1/videos/{id}/like → 200 {liked: false, like_count: N}
Duplicate like is idempotent (returns 200, count unchanged)
Like on unknown video → 404
Like on unknown user → 404

POST /api/v1/videos/{id}/comments → 201 with comment data
GET /api/v1/videos/{id}/comments → 200 paginated list
Empty comment text → 422
Comment on unknown video → 404
"""

from verify.acceptance.conftest import (
    assert_200,
    assert_404,
    assert_422,
    create_user,
    create_video,
    get_comments,
    like_video,
    post_comment,
    unlike_video,
)

# ---------------------------------------------------------------------------
# Like tests
# ---------------------------------------------------------------------------


def test_like_video_200(client):
    """Liking a video returns 200 with liked: true and incremented count."""
    user = create_user(client)
    video = create_video(client, user["user_id"])

    body = like_video(client, video["video_id"], user["user_id"])
    assert body["liked"] is True
    assert body["like_count"] == 1


def test_unlike_video_200(client):
    """Unliking a video returns 200 with liked: false and decremented count."""
    user = create_user(client)
    video = create_video(client, user["user_id"])

    like_video(client, video["video_id"], user["user_id"])
    body = unlike_video(client, video["video_id"], user["user_id"])

    assert body["liked"] is False
    assert body["like_count"] == 0


def test_duplicate_like_idempotent(client):
    """Liking the same video twice is idempotent — count stays at 1."""
    user = create_user(client)
    video = create_video(client, user["user_id"])

    first = like_video(client, video["video_id"], user["user_id"])
    assert first["like_count"] == 1

    second = like_video(client, video["video_id"], user["user_id"])
    assert second["liked"] is True
    assert second["like_count"] == 1  # unchanged


def test_unlike_without_like_200(client):
    """Unliking a video that was never liked is harmless (idempotent)."""
    user = create_user(client)
    video = create_video(client, user["user_id"])

    body = unlike_video(client, video["video_id"], user["user_id"])
    assert body["liked"] is False
    assert body["like_count"] == 0


def test_like_updates_video_detail_count(client):
    """Like count is reflected in video detail after liking."""
    user = create_user(client)
    author = create_user(client, username="author1")
    video = create_video(client, author["user_id"])

    like_video(client, video["video_id"], user["user_id"])

    r = client.get(f"/api/v1/videos/{video['video_id']}")
    detail = assert_200(r)
    assert detail["like_count"] == 1


def test_like_unknown_video_404(client):
    """Liking a non-existent video returns 404."""
    user = create_user(client)
    fake_video_id = "00000000-0000-0000-0000-000000000000"
    r = client.post(f"/api/v1/videos/{fake_video_id}/like", json={"user_id": user["user_id"]})
    assert_404(r)


def test_like_unknown_user_404(client):
    """Liking with a non-existent user returns 404."""
    user = create_user(client)
    video = create_video(client, user["user_id"])
    fake_user_id = "00000000-0000-0000-0000-000000000000"

    r = client.post(f"/api/v1/videos/{video['video_id']}/like", json={"user_id": fake_user_id})
    assert_404(r)


# ---------------------------------------------------------------------------
# Comment tests
# ---------------------------------------------------------------------------


def test_post_comment_201(client):
    """Posting a comment returns 201 with comment data."""
    user = create_user(client)
    author = create_user(client, username="creator")
    video = create_video(client, author["user_id"])

    body = post_comment(client, video["video_id"], user["user_id"], text="great video!")

    assert body["video_id"] == video["video_id"]
    assert body["user_id"] == user["user_id"]
    assert body["text"] == "great video!"
    assert "comment_id" in body
    assert "created_at" in body


def test_list_comments(client):
    """Listing comments returns paginated results."""
    user = create_user(client)
    author = create_user(client, username="creator")
    video = create_video(client, author["user_id"])

    c1 = post_comment(client, video["video_id"], user["user_id"], text="first")
    c2 = post_comment(client, video["video_id"], user["user_id"], text="second")

    body = get_comments(client, video["video_id"])

    assert "comments" in body
    assert isinstance(body["comments"], list)
    assert len(body["comments"]) >= 2

    comment_ids = {c["comment_id"] for c in body["comments"]}
    assert c1["comment_id"] in comment_ids
    assert c2["comment_id"] in comment_ids

    for c in body["comments"]:
        assert "text" in c
        assert "user" in c
        assert "created_at" in c


def test_comment_empty_text_422(client):
    """Posting a comment with empty text returns 422."""
    user = create_user(client)
    author = create_user(client, username="creator")
    video = create_video(client, author["user_id"])

    r = client.post(
        f"/api/v1/videos/{video['video_id']}/comments",
        json={"user_id": user["user_id"], "text": ""},
    )
    assert_422(r)


def test_comment_unknown_video_404(client):
    """Posting a comment on a non-existent video returns 404."""
    user = create_user(client)
    fake_video_id = "00000000-0000-0000-0000-000000000000"

    r = client.post(
        f"/api/v1/videos/{fake_video_id}/comments",
        json={"user_id": user["user_id"], "text": "hello"},
    )
    assert_404(r)


def test_comment_updates_video_count(client):
    """Comment count on video detail increments after posting."""
    user = create_user(client)
    author = create_user(client, username="creator")
    video = create_video(client, author["user_id"])

    post_comment(client, video["video_id"], user["user_id"], text="nice")

    r = client.get(f"/api/v1/videos/{video['video_id']}")
    detail = assert_200(r)
    assert detail["comment_count"] == 1


def test_comments_cursor_pagination(client):
    """Comment listing supports cursor-based pagination."""
    user = create_user(client)
    author = create_user(client, username="creator")
    video = create_video(client, author["user_id"])

    for i in range(3):
        post_comment(client, video["video_id"], user["user_id"], text=f"comment {i}")

    body = get_comments(client, video["video_id"])
    assert "next_cursor" in body
    assert len(body["comments"]) >= 1
