"""FR5: Follow creators and view their video catalog.

POST /api/v1/users → 201
GET /api/v1/users/{id} → 200
POST /api/v1/users/{id}/follow?follower_id=<uuid> → 200 {"status": "following"}
DELETE /api/v1/users/{id}/follow?follower_id=<uuid> → 200 {"status": "unfollowed"}
Duplicate follow is idempotent
Follow updates follower_count on both users
GET /api/v1/users/{id}/videos → 200 with cursor pagination
Self-follow → 422
Unknown user → 404
"""

from verify.acceptance.conftest import (
    assert_200,
    assert_404,
    assert_409,
    assert_422,
    create_user,
    create_video,
    follow_user,
    unfollow_user,
)


def test_create_user_201(client):
    """Creating a valid user returns 201 with user data."""
    body = create_user(client, username="tiktok_user")
    assert body["username"] == "tiktok_user"
    assert body["follower_count"] == 0
    assert body["following_count"] == 0
    assert "user_id" in body
    assert "created_at" in body


def test_create_user_duplicate_username_409(client):
    """Creating a user with an existing username returns 409."""
    create_user(client, username="unique_user")
    r = client.post("/api/v1/users", json={"username": "unique_user"})
    assert_409(r)


def test_create_user_empty_username_422(client):
    """Creating a user with empty username returns 422."""
    r = client.post("/api/v1/users", json={"username": ""})
    assert_422(r)


def test_get_user_200(client):
    """Fetching a user returns 200 with profile data."""
    user = create_user(client, username="profile_user")
    r = client.get(f"/api/v1/users/{user['user_id']}")
    body = assert_200(r)
    assert body["user_id"] == user["user_id"]
    assert body["username"] == "profile_user"


def test_get_user_unknown_404(client):
    """Fetching a non-existent user returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = client.get(f"/api/v1/users/{fake_id}")
    assert_404(r)


# ---------------------------------------------------------------------------
# Follow tests
# ---------------------------------------------------------------------------


def test_follow_200(client):
    """Following a creator returns 200 with status 'following'."""
    follower = create_user(client, username="follower1")
    creator = create_user(client, username="creator1")

    body = follow_user(client, creator["user_id"], follower["user_id"])
    assert body["status"] == "following"


def test_unfollow_200(client):
    """Unfollowing a creator returns 200 with status 'unfollowed'."""
    follower = create_user(client, username="follower2")
    creator = create_user(client, username="creator2")

    follow_user(client, creator["user_id"], follower["user_id"])
    body = unfollow_user(client, creator["user_id"], follower["user_id"])
    assert body["status"] == "unfollowed"


def test_duplicate_follow_idempotent(client):
    """Following the same creator twice is idempotent."""
    follower = create_user(client, username="follower3")
    creator = create_user(client, username="creator3")

    first = follow_user(client, creator["user_id"], follower["user_id"])
    second = follow_user(client, creator["user_id"], follower["user_id"])
    assert first["status"] == "following"
    assert second["status"] == "following"


def test_follow_updates_follower_count(client):
    """Following increments the followee's follower_count."""
    follower = create_user(client, username="follower4")
    creator = create_user(client, username="creator4")

    follow_user(client, creator["user_id"], follower["user_id"])

    r = client.get(f"/api/v1/users/{creator['user_id']}")
    body = assert_200(r)
    assert body["follower_count"] == 1

    r2 = client.get(f"/api/v1/users/{follower['user_id']}")
    body2 = assert_200(r2)
    assert body2["following_count"] == 1


def test_unfollow_decrements_follower_count(client):
    """Unfollowing decrements the followee's follower_count."""
    follower = create_user(client, username="follower5")
    creator = create_user(client, username="creator5")

    follow_user(client, creator["user_id"], follower["user_id"])
    unfollow_user(client, creator["user_id"], follower["user_id"])

    r = client.get(f"/api/v1/users/{creator['user_id']}")
    body = assert_200(r)
    assert body["follower_count"] == 0


def test_follow_unknown_followee_404(client):
    """Following a non-existent user returns 404."""
    follower = create_user(client, username="follower6")
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = client.post(
        f"/api/v1/users/{fake_id}/follow",
        params={"follower_id": follower["user_id"]},
    )
    assert_404(r)


def test_follow_unknown_follower_404(client):
    """Following with a non-existent follower returns 404."""
    creator = create_user(client, username="creator7")
    fake_follower_id = "00000000-0000-0000-0000-000000000000"
    r = client.post(
        f"/api/v1/users/{creator['user_id']}/follow",
        params={"follower_id": fake_follower_id},
    )
    assert_404(r)


def test_unfollow_without_follow_200(client):
    """Unfollowing someone you don't follow is harmless (idempotent)."""
    follower = create_user(client, username="follower8")
    creator = create_user(client, username="creator8")
    body = unfollow_user(client, creator["user_id"], follower["user_id"])
    assert body["status"] == "unfollowed"


# ---------------------------------------------------------------------------
# Creator catalog tests
# ---------------------------------------------------------------------------


def test_creator_catalog_returns_videos(client):
    """Creator's video catalog returns their published videos."""
    creator = create_user(client, username="creator10")
    v1 = create_video(client, creator["user_id"], caption="creator video 1")
    v2 = create_video(client, creator["user_id"], caption="creator video 2")

    r = client.get(f"/api/v1/users/{creator['user_id']}/videos")
    body = assert_200(r)

    assert "videos" in body
    video_ids = {v["video_id"] for v in body["videos"]}
    assert v1["video_id"] in video_ids
    assert v2["video_id"] in video_ids


def test_creator_catalog_pagination(client):
    """Creator catalog supports cursor pagination."""
    creator = create_user(client, username="creator11")
    for i in range(5):
        create_video(client, creator["user_id"], caption=f"vid {i}")

    r = client.get(f"/api/v1/users/{creator['user_id']}/videos")
    body = assert_200(r)
    assert "next_cursor" in body
    assert len(body["videos"]) >= 1


def test_creator_catalog_unknown_user_404(client):
    """Requesting catalog for unknown user returns 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = client.get(f"/api/v1/users/{fake_id}/videos")
    assert_404(r)
